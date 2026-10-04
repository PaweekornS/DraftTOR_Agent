"""Evaluate the TOR draft+compliance pipeline against the configured (real) LLM.

Suite A  checker   : seeded-defect TORs -> detection recall + false positives on a clean TOR
Suite B  e2e       : generate TORs from scratch -> pass rate, revisions, fallbacks, latency, LLM calls
Suite C  revise    : chapter edits by instruction -> adherence, isolation, compliance flagging

Usage: python scripts/eval_tor_compliance.py [--suites A,B,C] [--runs 3]
Writes data/eval/tor_eval_<timestamp>.json
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.llm_factory import call_llm
from app.tor.checks import load_rules, run_compliance
from app.tor.drafting import extract_facts
from app.tor.graph import build_tor_compliance_graph
from app.tor.regulations import get_regulation_index
from app.tor.schemas import (
    BOQItem, ChapterKind as K, DraftChapter, FindingStatus, Installment, ProcurementMethod,
    ProcurementType, TemplateChapter, TORRequest, TORTemplateSpec,
)
from app.tor.service import AuditLog, revise_chapter


class CountingLLM:
    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self.calls = 0
        self.empty = 0

    def __call__(self, messages):
        with self._lock:
            self.calls += 1
        out = call_llm(messages)
        if not out:
            with self._lock:
                self.empty += 1
        return out


TEMPLATE = TORTemplateSpec(template_id="ebidding_service_over_500k", chapters=[
    TemplateChapter(id="background", title="ความเป็นมาและเหตุผลความจำเป็น", kind=K.TEXT),
    TemplateChapter(id="objectives", title="วัตถุประสงค์", kind=K.LIST),
    TemplateChapter(id="qualifications", title="คุณสมบัติของผู้ยื่นข้อเสนอ", kind=K.LIST,
                    instructions="รวมคุณสมบัติทั่วไปตามกฎหมายและคุณสมบัติเฉพาะด้านผลงาน"),
    TemplateChapter(id="spec", title="ขอบเขตของงานและคุณลักษณะเฉพาะ", kind=K.LIST),
    TemplateChapter(id="budget", title="วงเงินงบประมาณและรายละเอียดค่าใช้จ่าย", kind=K.BOQ),
    TemplateChapter(id="payment", title="งวดงานและการจ่ายเงิน", kind=K.PAYMENT_SCHEDULE),
    TemplateChapter(id="terms", title="หลักประกันสัญญา ค่าปรับ และการจ้างช่วง", kind=K.TEXT,
                    instructions="กำหนดหลักประกันสัญญา อัตราค่าปรับรายวัน และข้อห้ามจ้างช่วงพร้อมค่าปรับ"),
])


def request(**kw) -> TORRequest:
    base = dict(project_name="โครงการพัฒนาระบบสืบค้นเอกสารราชการอัจฉริยะ", agency_name="สำนักงานพัฒนารัฐบาลดิจิทัล",
                budget=3_500_000, duration_days=240, procurement_type=ProcurementType.SERVICES, template=TEMPLATE,
                raw_requirements="ระบบค้นหาเอกสารราชการด้วย AI รองรับภาษาไทย พร้อมติดตั้งบนคลาวด์ภาครัฐ อบรมผู้ใช้ และดูแลระบบ 1 ปี")
    base.update(kw)
    return TORRequest(**base)


# ---------------- Suite A: seeded defects ----------------
def clean_chapters():
    return [
        DraftChapter(id="background", title="ความเป็นมา", kind=K.TEXT,
                     text="หน่วยงานมีเอกสารราชการจำนวนมากที่ค้นหาได้ยาก จึงมีความจำเป็นต้องพัฒนาระบบสืบค้นอัจฉริยะเพื่อเพิ่มประสิทธิภาพการปฏิบัติงานและการให้บริการประชาชน"),
        DraftChapter(id="objectives", title="วัตถุประสงค์", kind=K.LIST,
                     items=["เพื่อพัฒนาระบบสืบค้นเอกสารราชการที่รองรับภาษาไทย", "เพื่อลดระยะเวลาการค้นหาเอกสารของเจ้าหน้าที่"]),
        DraftChapter(id="qualifications", title="คุณสมบัติของผู้ยื่นข้อเสนอ", kind=K.LIST, items=[
            "มีความสามารถตามกฎหมาย และไม่เป็นบุคคลล้มละลาย",
            "ไม่เป็นบุคคลซึ่งถูกระบุชื่อไว้ในบัญชีรายชื่อผู้ทิ้งงานของทางราชการ",
            "เป็นนิติบุคคลผู้มีอาชีพรับจ้างงานที่ประกวดราคาอิเล็กทรอนิกส์ดังกล่าว",
            "มีผลงานพัฒนาระบบสารสนเทศในวงเงินไม่น้อยกว่า 1,500,000 บาท ในสัญญาเดียว"]),
        DraftChapter(id="spec", title="ขอบเขตของงาน", kind=K.LIST, items=[
            "ระบบต้องรองรับการค้นหาเอกสารภาษาไทยแบบความหมาย (Semantic Search)",
            "เครื่องแม่ข่ายมีหน่วยประมวลผลไม่น้อยกว่า 32 แกน หน่วยความจำไม่น้อยกว่า 256 GB หรือดีกว่า",
            "ระบบต้องรองรับผู้ใช้งานพร้อมกันไม่น้อยกว่า 500 ราย",
            "จัดฝึกอบรมผู้ใช้งานไม่น้อยกว่า 2 รุ่น"]),
        DraftChapter(id="budget", title="งบประมาณ", kind=K.BOQ, boq=[
            BOQItem(name="ค่าพัฒนาระบบ", unit_price=2_500_000, total_price=2_500_000),
            BOQItem(name="ค่าฝึกอบรม", unit_price=1_000_000, total_price=1_000_000)]),
        DraftChapter(id="payment", title="งวดงาน", kind=K.PAYMENT_SCHEDULE, installments=[
            Installment(no=1, percent=30, deliverable="แผนงานและเอกสารออกแบบ", due_day=60),
            Installment(no=2, percent=70, deliverable="ระบบที่ติดตั้งแล้วและรายงานอบรม", due_day=240)]),
        DraftChapter(id="terms", title="หลักประกันและค่าปรับ", kind=K.TEXT, text=(
            "ผู้ชนะการเสนอราคาต้องวางหลักประกันสัญญาร้อยละ 5 ของราคาค่าจ้าง กรณีส่งมอบงานล่าช้า "
            "จะต้องชำระค่าปรับเป็นรายวันในอัตราร้อยละ 0.1 ของราคางานจ้างที่ยังไม่ได้รับมอบ "
            "ห้ามผู้รับจ้างจ้างช่วงงานโดยไม่ได้รับอนุญาต หากฝ่าฝืนต้องชำระค่าปรับร้อยละ 10 ของวงเงินที่จ้างช่วง")),
    ]


def mutate(chapters, cid, **update):
    return [c.model_copy(update=update) if c.id == cid else c for c in chapters]


def add_item(chapters, cid, item):
    return [c.model_copy(update={"items": c.items + [item]}) if c.id == cid else c for c in chapters]


def replace_text(chapters, cid, old, new):
    out = []
    for c in chapters:
        if c.id == cid:
            c = c.model_copy(update={"text": c.text.replace(old, new),
                                     "items": [i.replace(old, new) for i in c.items]})
        out.append(c)
    return out


def seeded_cases():
    base = clean_chapters()
    E = ProcurementMethod.E_BIDDING
    return [
        # (case_id, category, expected_rule, chapters, method, budget)
        ("brand_explicit", "semantic", "SPEC_NO_BRAND_LOCK",
         add_item(base, "spec", "เครื่องแม่ข่าย Dell PowerEdge R760 จำนวน 2 เครื่อง"), E, None),
        ("brand_software_only", "semantic", "SPEC_NO_BRAND_LOCK",
         add_item(base, "spec", "ฐานข้อมูลต้องเป็น Oracle Database Enterprise Edition เท่านั้น"), E, None),
        ("brand_cpu_model", "semantic", "SPEC_NO_BRAND_LOCK",
         add_item(base, "spec", "หน่วยประมวลผล Intel Xeon Gold 6430 จำนวน 2 ตัว"), E, None),
        ("brand_implicit_proprietary", "semantic", "SPEC_NO_BRAND_LOCK",
         add_item(base, "spec", "ระบบต้องทำงานบนระบบปฏิบัติการ iOS และเชื่อมต่อผ่าน Lightning port เท่านั้น"), E, None),
        ("qual_dealer_lock", "semantic", "QUALIFICATIONS_PROPORTIONATE",
         add_item(base, "qualifications", "ต้องได้รับการแต่งตั้งเป็นตัวแทนจำหน่ายโดยตรงจากบริษัท ไมโครซอฟท์ (ประเทศไทย) จำกัด"), E, None),
        ("qual_capital_excessive", "semantic", "QUALIFICATIONS_PROPORTIONATE",
         add_item(base, "qualifications", "ต้องมีทุนจดทะเบียนชำระแล้วไม่น้อยกว่า 200,000,000 บาท"), E, None),
        ("qual_location", "semantic", "QUALIFICATIONS_PROPORTIONATE",
         add_item(base, "qualifications", "ต้องมีสำนักงานใหญ่ตั้งอยู่ในจังหวัดเชียงใหม่เท่านั้น"), E, None),
        ("penalty_too_high", "facts", "PENALTY_RATE_RANGE",
         replace_text(base, "terms", "ร้อยละ 0.1 ของราคางาน", "ร้อยละ 0.5 ของราคางาน"), E, None),
        ("bond_too_low", "facts", "PERFORMANCE_BOND_RATE",
         replace_text(base, "terms", "หลักประกันสัญญาร้อยละ 5", "หลักประกันสัญญาร้อยละ 3"), E, None),
        ("subcontract_penalty_low", "facts", "SUBCONTRACT_PENALTY_MIN",
         replace_text(base, "terms", "ค่าปรับร้อยละ 10 ของวงเงินที่จ้างช่วง", "ค่าปรับร้อยละ 5 ของวงเงินที่จ้างช่วง"), E, None),
        ("reference_work_80pct", "facts", "REFERENCE_WORK_MAX_50PCT",
         replace_text(base, "qualifications", "1,500,000", "2,800,000"), E, None),
        ("installments_110", "deterministic", "INSTALLMENTS_SUM_100",
         mutate(base, "payment", installments=[Installment(no=1, percent=40, deliverable="a", due_day=60),
                                               Installment(no=2, percent=70, deliverable="b", due_day=240)]), E, None),
        ("boq_mismatch", "deterministic", "BOQ_SUM_EQUALS_BUDGET",
         mutate(base, "budget", boq=[BOQItem(name="ค่าพัฒนาระบบ", unit_price=2_500_000, total_price=2_500_000),
                                     BOQItem(name="ค่าฝึกอบรม", unit_price=900_000, total_price=900_000)]), E, None),
        ("ebidding_wording_specific", "deterministic", "METHOD_TERMINOLOGY_CONSISTENT",
         base, ProcurementMethod.SPECIFIC, 450_000),
    ]


def near_miss_cases():
    """Compliant edits that look suspicious. The named rule must NOT fail on these."""
    base = clean_chapters()
    E = ProcurementMethod.E_BIDDING
    return [
        ("nm_or_equivalent", "semantic", "SPEC_NO_BRAND_LOCK",
         add_item(base, "spec", "ซอฟต์แวร์ฐานข้อมูลเชิงสัมพันธ์ที่รองรับมาตรฐาน SQL:2016 หรือเทียบเท่า"), E, None),
        ("nm_multi_platform", "semantic", "SPEC_NO_BRAND_LOCK",
         add_item(base, "spec", "ระบบต้องใช้งานได้บนเว็บเบราว์เซอร์ทั่วไป เช่น Chrome, Edge, Firefox และ Safari"), E, None),
        ("nm_open_standard", "semantic", "SPEC_NO_BRAND_LOCK",
         add_item(base, "spec", "ระบบต้องผ่านการทดสอบความปลอดภัยตามแนวทาง OWASP Top 10"), E, None),
        ("nm_iso_cert", "semantic", "QUALIFICATIONS_PROPORTIONATE",
         add_item(base, "qualifications", "มีบุคลากรผู้เชี่ยวชาญด้านความมั่นคงปลอดภัยสารสนเทศอย่างน้อย 1 คน"), E, None),
        ("nm_reference_50pct", "facts", "REFERENCE_WORK_MAX_50PCT",
         replace_text(base, "qualifications", "1,500,000", "1,750,000"), E, None),
        ("nm_penalty_upper_bound", "facts", "PENALTY_RATE_RANGE",
         replace_text(base, "terms", "ร้อยละ 0.1 ของราคางาน", "ร้อยละ 0.2 ของราคางาน"), E, None),
    ]


def _flagged(findings, rule_id, verified):
    ok = {FindingStatus.FAIL} if verified[rule_id] else {FindingStatus.FAIL, FindingStatus.NEEDS_HUMAN}
    return [x for x in findings if x.rule_id == rule_id and x.status in ok]


def suite_a(runs: int):
    index = get_regulation_index()
    verified = {r.id: r.verified for r in load_rules().rules}
    cases = [(c, True) for c in seeded_cases()] + [(c, False) for c in near_miss_cases()]
    rows, fp_rows = [], []
    for r in range(runs):
        # clean baseline -> false positives
        llm = CountingLLM()
        req = request()
        facts = extract_facts(clean_chapters(), llm)
        f = run_compliance(req, ProcurementMethod.E_BIDDING, clean_chapters(), facts, index, llm)
        flagged = sorted({x.rule_id for x in f if x.status in (FindingStatus.FAIL, FindingStatus.NEEDS_HUMAN)})
        fp_rows.append({"run": r, "flagged": flagged, "facts": facts.model_dump()})
        print(f"[A] run {r} clean baseline flagged: {flagged or 'none'}")

        for (cid, cat, expected, chapters, method, budget), should_flag in cases:
            llm = CountingLLM()
            req = request(budget=budget) if budget else request()
            if budget:  # keep BOQ consistent with the smaller budget so only the seeded defect remains
                chapters = mutate(chapters, "budget", boq=[BOQItem(name="ค่าพัฒนาระบบ", unit_price=budget, total_price=budget)])
            facts = extract_facts(chapters, llm)
            f = run_compliance(req, method, chapters, facts, index, llm)
            hits = _flagged(f, expected, verified)
            others = sorted({x.rule_id for x in f if x.rule_id != expected
                             and x.status in (FindingStatus.FAIL, FindingStatus.NEEDS_HUMAN)})
            rows.append({"run": r, "case": cid, "category": cat, "expected": expected, "should_flag": should_flag,
                         "detected": bool(hits), "correct": bool(hits) == should_flag,
                         "status": hits[0].status.value if hits else None,
                         "evidence": hits[0].evidence if hits else None, "other_flags": others,
                         "facts": facts.model_dump(), "llm_calls": llm.calls, "llm_empty": llm.empty})
            verdict = ("DETECTED" if hits else "MISSED  ") if should_flag else ("FALSE+  " if hits else "OK(neg) ")
            print(f"[A] run {r} {cid:28s} {verdict} others={others}")
    return {"cases": rows, "clean_baseline": fp_rows}


# ---------------- Suite B: end-to-end ----------------
def e2e_requests():
    return {
        "service_ebidding_3.5M": request(),
        "goods_specific_300k": request(
            project_name="โครงการจัดซื้อเครื่องคอมพิวเตอร์โน้ตบุ๊กสำหรับเจ้าหน้าที่", budget=300_000, duration_days=60,
            procurement_type=ProcurementType.GOODS,
            raw_requirements="จัดซื้อเครื่องคอมพิวเตอร์โน้ตบุ๊ก 10 เครื่อง สำหรับงานสำนักงาน พร้อมรับประกัน 3 ปี"),
        "consulting_2M": request(
            project_name="โครงการจ้างที่ปรึกษาจัดทำแผนแม่บทดิจิทัล", budget=2_000_000, duration_days=180,
            procurement_type=ProcurementType.CONSULTING,
            raw_requirements="จ้างที่ปรึกษาศึกษาและจัดทำแผนแม่บทเทคโนโลยีดิจิทัล 5 ปี พร้อมจัดประชุมรับฟังความคิดเห็น"),
    }


def suite_b(runs: int):
    rows, results = [], {}
    for r in range(runs):
        for name, req in e2e_requests().items():
            llm = CountingLLM()
            t = time.time()
            res = build_tor_compliance_graph(llm=llm).invoke({"request": req})["result"]
            rep = res.report
            row = {"run": r, "request": name, "method": rep.procurement_method.value, "passed": rep.passed,
                   "revisions": rep.revisions, "summary": rep.summary(),
                   "blocking": [f.key for f in rep.blocking],
                   "needs_human": [f.key for f in rep.findings if f.status == FindingStatus.NEEDS_HUMAN],
                   "warn": [f.key for f in rep.findings if f.status == FindingStatus.WARN],
                   "fallback_chapters": [c.id for c in res.chapters if c.used_fallback],
                   "seconds": round(time.time() - t, 1), "llm_calls": llm.calls, "llm_empty": llm.empty}
            rows.append(row)
            results[f"{name}#{r}"] = res
            print(f"[B] run {r} {name:24s} passed={rep.passed} rev={rep.revisions} "
                  f"blocking={row['blocking']} {row['seconds']}s calls={llm.calls}")
    return {"rows": rows}, results


# ---------------- Suite C: revise_chapter ----------------
REVISIONS = [
    # (chapter, instruction, must_contain_any, expected_flag or None)
    ("spec", "เพิ่มข้อกำหนดว่าระบบต้องมีความพร้อมใช้งาน (availability) ไม่น้อยกว่าร้อยละ 99.9", ["99.9"], None),
    ("payment", "แบ่งงวดใหม่เป็น 3 งวด ร้อยละ 20, 30 และ 50", ["3งวด"], None),
    ("spec", "ระบุให้ใช้เครื่องแม่ข่ายยี่ห้อ Dell รุ่น PowerEdge R760", ["Dell"], "SPEC_NO_BRAND_LOCK"),
]


def suite_c(base_results, audit_dir: str):
    rows = []
    bases = [v for k, v in base_results.items() if k.startswith("service_ebidding")]
    if not bases:
        return {"rows": rows}
    base = bases[0]
    for cid, instruction, must, expected_flag in REVISIONS:
        llm = CountingLLM()
        t = time.time()
        out = revise_chapter(base, cid, instruction, actor="eval", llm=llm, audit=AuditLog(audit_dir))
        new = next(c for c in out.chapters if c.id == cid)
        text = new.as_plain_text().replace(" ", "")
        if cid == "payment":
            adhered = [round(i.percent) for i in new.installments] == [20, 30, 50]
        else:
            adhered = any(m.replace(" ", "") in text for m in must)
        isolated = [c for c in out.chapters if c.id != cid] == [c for c in base.chapters if c.id != cid]
        flagged = None
        if expected_flag:
            flagged = any(f.rule_id == expected_flag and f.status == FindingStatus.FAIL for f in out.report.findings)
        rows.append({"chapter": cid, "instruction": instruction, "adhered": adhered, "isolated": isolated,
                     "expected_flag": expected_flag, "flagged": flagged, "fallback": new.used_fallback,
                     "after": new.as_plain_text()[:600], "seconds": round(time.time() - t, 1), "llm_calls": llm.calls})
        print(f"[C] {cid:8s} adhered={adhered} isolated={isolated} flagged={flagged} {rows[-1]['seconds']}s")
    return {"rows": rows}


def summarize(report):
    s = {}
    if "A" in report:
        by_cat, by_case = defaultdict(list), defaultdict(list)
        pos = [r for r in report["A"]["cases"] if r["should_flag"]]
        neg = [r for r in report["A"]["cases"] if not r["should_flag"]]
        for row in pos:
            by_cat[row["category"]].append(row["detected"])
        for row in report["A"]["cases"]:
            by_case[row["case"]].append(row["correct"])
        allv = [r["detected"] for r in pos]
        s["A_recall_overall"] = round(sum(allv) / len(allv), 3)
        s["A_near_miss_false_positive_rate"] = round(sum(r["detected"] for r in neg) / len(neg), 3) if neg else None
        s["A_recall_by_category"] = {k: round(sum(v) / len(v), 3) for k, v in by_cat.items()}
        s["A_correct_by_case"] = {k: f"{sum(v)}/{len(v)}" for k, v in by_case.items()}
        s["A_clean_false_positive_runs"] = sum(1 for r in report["A"]["clean_baseline"] if r["flagged"])
        s["A_clean_runs"] = len(report["A"]["clean_baseline"])
        s["A_collateral_flags"] = sum(1 for r in report["A"]["cases"] if r["other_flags"])
    if "B" in report:
        rows = report["B"]["rows"]
        s["B_pass_rate"] = f"{sum(r['passed'] for r in rows)}/{len(rows)}"
        s["B_mean_revisions"] = round(sum(r["revisions"] for r in rows) / len(rows), 2)
        s["B_fallback_chapters"] = sum(len(r["fallback_chapters"]) for r in rows)
        s["B_mean_seconds"] = round(sum(r["seconds"] for r in rows) / len(rows), 1)
        s["B_mean_llm_calls"] = round(sum(r["llm_calls"] for r in rows) / len(rows), 1)
    if "C" in report:
        rows = report["C"]["rows"]
        s["C_adherence"] = f"{sum(r['adhered'] for r in rows)}/{len(rows)}"
        s["C_isolation"] = f"{sum(r['isolated'] for r in rows)}/{len(rows)}"
        flags = [r for r in rows if r["expected_flag"]]
        s["C_post_edit_flagging"] = f"{sum(bool(r['flagged']) for r in flags)}/{len(flags)}"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", default="A,B,C")
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    suites = set(args.suites.split(","))
    out_dir = Path("data/eval")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {"model": os.environ.get("LLM_MODEL_NAME") or __import__("app.config").config.settings.LLM_MODEL_NAME,
              "runs": args.runs, "started": stamp}
    if "A" in suites:
        report["A"] = suite_a(args.runs)
    base_results = {}
    if "B" in suites or "C" in suites:
        report["B"], base_results = suite_b(args.runs if "B" in suites else 1)
    if "C" in suites:
        report["C"] = suite_c(base_results, str(out_dir / f"audit_{stamp}"))
    report["summary"] = summarize(report)
    path = out_dir / f"tor_eval_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\nFull report: {path}")


if __name__ == "__main__":
    main()
