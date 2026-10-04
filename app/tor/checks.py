"""Rule registry loading and check implementations.

Each check receives a CheckContext and returns a list of Findings. Checks never raise on
missing data: an absent fact is reported (WARN) rather than silently passed.
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel

from app.config import settings
from app.tor.concurrency import JudgeCache, pmap, stable_hash
from app.tor.llm import LLMFn, call_structured
from app.tor.regulations import RegulationIndex
from app.tor.schemas import (
    ChapterKind, Citation, DraftChapter, Finding, FindingStatus, ProcurementMethod,
    ProcurementType, Severity, TORFacts, TORRequest,
)


# ----------------- registry -----------------
class Rule(BaseModel):
    id: str
    title: str
    check: str
    severity: Severity
    params: Dict[str, Any] = {}
    applies_to: Dict[str, List[str]] = {}
    citation: Optional[Dict[str, str]] = None
    verified: bool = False
    note: Optional[str] = None

    def applies(self, ptype: ProcurementType, method: ProcurementMethod) -> bool:
        types = self.applies_to.get("procurement_types") or []
        methods = self.applies_to.get("methods") or []
        return (not types or ptype.value in types) and (not methods or method.value in methods)


class RuleRegistry(BaseModel):
    version: str
    rules: List[Rule]


@lru_cache(maxsize=4)
def load_rules(path: Optional[str] = None) -> RuleRegistry:
    with open(path or settings.TOR_RULES_PATH, encoding="utf-8") as f:
        registry = RuleRegistry(**yaml.safe_load(f))
    unknown = [r.check for r in registry.rules if r.check not in CHECKS]
    if unknown:
        raise ValueError(f"Rule registry references unknown checks: {unknown}")
    return registry


# ----------------- context -----------------
@dataclass
class CheckContext:
    req: TORRequest
    method: ProcurementMethod
    chapters: List[DraftChapter]
    facts: TORFacts
    rule: Rule
    index: RegulationIndex
    llm: Optional[LLMFn] = None
    judge_cache: Optional[JudgeCache] = None
    _citation: Optional[Citation] = field(default=None, init=False)

    @property
    def citation(self) -> Optional[Citation]:
        if self._citation is None and self.rule.citation:
            c = self.index.get_clause(self.rule.citation["doc"], self.rule.citation["clause"])
            self._citation = Citation(
                doc=self.rule.citation["doc"],
                clause=self.rule.citation["clause"],
                text=c.text if c else None,
            )
        return self._citation

    def finding(self, status: FindingStatus, message: str, **kw) -> Finding:
        if not self.rule.verified and status == FindingStatus.FAIL:
            status = FindingStatus.NEEDS_HUMAN
            message = f"[กฎยังไม่ผ่านการยืนยัน] {message}"
        return Finding(
            rule_id=self.rule.id, title=self.rule.title, severity=self.rule.severity,
            status=status, message=message, citation=self.citation, **kw,
        )

    def ok(self, message: str = "ผ่าน") -> List[Finding]:
        return [self.finding(FindingStatus.PASS, message)]

    def missing_fact(self, what: str, suggestion: str) -> List[Finding]:
        """A fact the rule needs is absent. Never a silent pass."""
        if not self.facts.extraction_ok:
            return [self.finding(FindingStatus.NEEDS_HUMAN,
                                 f"ตัวสกัดข้อมูลทำงานไม่สำเร็จ ไม่สามารถยืนยัน{what}ได้ ต้องให้เจ้าหน้าที่ตรวจ")]
        return [self.finding(FindingStatus.WARN, f"ไม่พบการกำหนด{what}ในเอกสาร", suggestion=suggestion)]

    def chapters_of(self, kind: ChapterKind) -> List[DraftChapter]:
        return [c for c in self.chapters if c.kind == kind]


Check = Callable[[CheckContext], List[Finding]]
CHECKS: Dict[str, Check] = {}


def check(name: str):
    def deco(fn: Check) -> Check:
        CHECKS[name] = fn
        return fn
    return deco


# ----------------- deterministic checks -----------------
@check("chapters_complete")
def chapters_complete(ctx: CheckContext) -> List[Finding]:
    drafted = {c.id: c for c in ctx.chapters}
    out = []
    for spec in ctx.req.template.chapters:
        ch = drafted.get(spec.id)
        if spec.required and (ch is None or not ch.as_plain_text().strip()):
            out.append(ctx.finding(FindingStatus.FAIL, f"บท '{spec.title}' ไม่มีเนื้อหา", chapter_id=spec.id))
    return out or ctx.ok(f"ครบ {len(ctx.req.template.chapters)} บท")


@check("no_fallback_content")
def no_fallback_content(ctx: CheckContext) -> List[Finding]:
    out = [ctx.finding(FindingStatus.FAIL, f"บท '{c.title}' ใช้ข้อความสำรองเนื่องจาก LLM ร่างไม่สำเร็จ",
                       chapter_id=c.id, suggestion="ร่างบทนี้ใหม่หรือให้เจ้าหน้าที่เขียนเอง")
           for c in ctx.chapters if c.used_fallback]
    return out or ctx.ok()


@check("boq_sum_equals_budget")
def boq_sum_equals_budget(ctx: CheckContext) -> List[Finding]:
    out = []
    for ch in ctx.chapters_of(ChapterKind.BOQ):
        if not ch.boq:
            out.append(ctx.finding(FindingStatus.FAIL, "ตารางงบประมาณว่างเปล่า", chapter_id=ch.id))
            continue
        bad_rows = [b.name for b in ch.boq if abs(b.qty * b.unit_price - b.total_price) > 0.01]
        if bad_rows:
            out.append(ctx.finding(FindingStatus.FAIL, f"จำนวน x ราคาต่อหน่วย ไม่เท่ากับราคารวม: {bad_rows}",
                                   chapter_id=ch.id))
        total = round(sum(b.total_price for b in ch.boq), 2)
        if abs(total - ctx.req.budget) > ctx.rule.params.get("tolerance_baht", 0.01):
            out.append(ctx.finding(
                FindingStatus.FAIL,
                f"ผลรวม {total:,.2f} บาท ไม่เท่ากับวงเงิน {ctx.req.budget:,.2f} บาท",
                chapter_id=ch.id, evidence=f"ส่วนต่าง {total - ctx.req.budget:,.2f} บาท",
            ))
    return out or ctx.ok()


@check("installments_sum_100")
def installments_sum_100(ctx: CheckContext) -> List[Finding]:
    out = []
    for ch in ctx.chapters_of(ChapterKind.PAYMENT_SCHEDULE):
        total = round(sum(i.percent for i in ch.installments), 4)
        if not ch.installments or abs(total - 100) > 1e-6:
            out.append(ctx.finding(FindingStatus.FAIL, f"ร้อยละรวมทุกงวด = {total:g} (ต้องเท่ากับ 100)",
                                   chapter_id=ch.id, suggestion="ปรับร้อยละของแต่ละงวดให้รวมเป็น 100"))
    return out or ctx.ok()


@check("installments_within_duration")
def installments_within_duration(ctx: CheckContext) -> List[Finding]:
    out = []
    for ch in ctx.chapters_of(ChapterKind.PAYMENT_SCHEDULE):
        days = [i.due_day for i in sorted(ch.installments, key=lambda i: i.no)]
        if days != sorted(days):
            out.append(ctx.finding(FindingStatus.FAIL, f"กำหนดส่งมอบไม่เรียงตามลำดับงวด: {days}", chapter_id=ch.id))
        late = [i.no for i in ch.installments if i.due_day > ctx.req.duration_days]
        if late:
            out.append(ctx.finding(FindingStatus.FAIL,
                                   f"งวดที่ {late} เกินระยะเวลาดำเนินงาน {ctx.req.duration_days} วัน",
                                   chapter_id=ch.id))
    return out or ctx.ok()


@check("method_terminology")
def method_terminology(ctx: CheckContext) -> List[Finding]:
    forbidden = ctx.rule.params.get("forbidden_by_method", {}).get(ctx.method.value, [])
    out = []
    for ch in ctx.chapters:
        text = ch.as_plain_text()
        for phrase in forbidden:
            if phrase.lower() in text.lower():
                out.append(ctx.finding(
                    FindingStatus.FAIL,
                    f"พบคำว่า '{phrase}' แต่โครงการนี้ใช้วิธี {ctx.method.value}",
                    chapter_id=ch.id, evidence=_snippet(text, phrase),
                    suggestion="แก้ถ้อยคำให้ตรงกับวิธีจัดซื้อจัดจ้างที่ใช้จริง",
                ))
    return out or ctx.ok()


@check("penalty_rate_range")
def penalty_rate_range(ctx: CheckContext) -> List[Finding]:
    rate = ctx.facts.penalty_rate_pct_per_day
    lo, hi = ctx.rule.params["consulting_range" if ctx.req.procurement_type == ProcurementType.CONSULTING
                             else "default_range"]
    if rate is None:
        return ctx.missing_fact("อัตราค่าปรับรายวัน",
                                f"กำหนดค่าปรับรายวันร้อยละ {lo}-{hi} ของราคาพัสดุ/งานที่ยังไม่ได้รับมอบ")
    if not lo <= rate <= hi:
        return [ctx.finding(FindingStatus.FAIL, f"อัตราค่าปรับร้อยละ {rate:g} ต่อวัน อยู่นอกช่วง {lo}-{hi}",
                            suggestion=f"ปรับเป็นร้อยละ {lo}-{hi} ต่อวัน")]
    return ctx.ok(f"ค่าปรับร้อยละ {rate:g} ต่อวัน")


@check("bond_rate")
def bond_rate(ctx: CheckContext) -> List[Finding]:
    std, mx = ctx.rule.params["standard_pct"], ctx.rule.params["max_pct"]
    if ctx.facts.performance_bond_pct is None and ctx.facts.bid_bond_pct is None:
        return ctx.missing_fact("หลักประกันสัญญา", f"กำหนดหลักประกันสัญญาร้อยละ {std}")
    out = []
    for name, val in (("หลักประกันสัญญา", ctx.facts.performance_bond_pct),
                      ("หลักประกันการเสนอราคา", ctx.facts.bid_bond_pct)):
        if val is None:
            continue
        if val < std or val > mx:
            out.append(ctx.finding(FindingStatus.FAIL, f"{name} ร้อยละ {val:g} (ต้องเป็นร้อยละ {std}, สูงสุด {mx})"))
        elif val > std:
            out.append(ctx.finding(FindingStatus.WARN,
                                   f"{name} ร้อยละ {val:g} สูงกว่าร้อยละ {std} ต้องมีเหตุผลว่าสำคัญเป็นพิเศษ"))
    return out or ctx.ok()


@check("subcontract_penalty")
def subcontract_penalty(ctx: CheckContext) -> List[Finding]:
    pct, min_pct = ctx.facts.subcontract_penalty_pct, ctx.rule.params["min_pct"]
    if pct is None:
        return ctx.missing_fact("ค่าปรับกรณีจ้างช่วงโดยไม่ได้รับอนุญาต",
                                f"เพิ่มข้อห้ามจ้างช่วงพร้อมค่าปรับไม่น้อยกว่าร้อยละ {min_pct}")
    if pct < min_pct:
        return [ctx.finding(FindingStatus.FAIL, f"ค่าปรับจ้างช่วงร้อยละ {pct:g} ต่ำกว่าร้อยละ {min_pct}")]
    return ctx.ok()


@check("reference_work_cap")
def reference_work_cap(ctx: CheckContext) -> List[Finding]:
    v = ctx.facts.min_reference_work_value
    if v is None:
        if not ctx.facts.extraction_ok:
            return ctx.missing_fact("มูลค่าผลงานอ้างอิง", "")
        return ctx.ok("ไม่ได้กำหนดมูลค่าผลงานอ้างอิง")
    cap = ctx.req.budget * ctx.rule.params["max_ratio"]
    if v > cap:
        return [ctx.finding(FindingStatus.FAIL, f"ผลงานอ้างอิง {v:,.2f} บาท เกิน {cap:,.2f} บาท",
                            suggestion=f"ลดมูลค่าผลงานอ้างอิงให้ไม่เกิน {cap:,.2f} บาท")]
    return ctx.ok()


@check("specific_method_cap")
def specific_method_cap(ctx: CheckContext) -> List[Finding]:
    cap = ctx.rule.params["max_budget"]
    if ctx.req.budget > cap:
        return [ctx.finding(FindingStatus.FAIL,
                            f"วงเงิน {ctx.req.budget:,.2f} บาท เกิน {cap:,} บาท แต่ใช้วิธีเฉพาะเจาะจง "
                            "ต้องอ้างเหตุตามมาตรา ๕๖ (๒) ข้ออื่น")]
    return ctx.ok()


# ----------------- LLM-as-judge -----------------
class Violation(BaseModel):
    chapter_id: str
    quote: str
    reason: str
    suggestion: str


class JudgeResult(BaseModel):
    violations: List[Violation]


class ChecklistAnswer(BaseModel):
    item: int
    violated: bool
    quote: str = ""
    reason: str = ""
    suggestion: str = ""


class ChecklistResult(BaseModel):
    answers: List[ChecklistAnswer]


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


@check("llm_judge")
def llm_judge(ctx: CheckContext) -> List[Finding]:
    """Judge each in-scope chapter independently: parallel, and cacheable per chapter text."""
    kinds = set(ctx.rule.params.get("chapter_kinds", [k.value for k in ChapterKind]))
    targets = [c for c in ctx.chapters if c.kind.value in kinds and c.as_plain_text().strip()]
    # Narrow to chapters whose title matches the rule's scope (template titles vary; fall back to all).
    title_kw = ctx.rule.params.get("chapter_title_keywords") or []
    scoped = [c for c in targets if any(k in c.title for k in title_kw)]
    targets = scoped or targets
    if not targets:
        return ctx.ok("ไม่มีบทที่ต้องตรวจ")
    per_chapter = pmap(lambda c: _judge_chapter(ctx, c), targets)
    out = [f for fs in per_chapter for f in fs]
    failing = [f for f in out if f.status != FindingStatus.PASS]
    return failing or ctx.ok()


def _answer_format(ctx: CheckContext, ch: DraftChapter) -> str:
    checklist = ctx.rule.params.get("checklist")
    if checklist:
        items = "\n".join(f"{i}. {c}" for i, c in enumerate(checklist, 1))
        return f"""ตอบทุกข้อของรายการตรวจต่อไปนี้ (ข้อละ 1 คำตอบ ครบ {len(checklist)} ข้อ):
{items}

- violated = true เมื่อบทนี้มีข้อความที่เข้าข่ายข้อนั้น
- ถ้า violated = true ต้องคัดลอกข้อความที่เข้าข่ายจากบทนี้มาใส่ quote ตรงตัวอักษร และเสนอถ้อยคำแก้ไขใน suggestion"""
    return f"""ข้อกำหนดการตอบ:
- รายงานเฉพาะการละเมิดที่ชัดเจน ถ้าไม่มีให้ตอบ violations เป็นรายการว่าง
- chapter_id ให้ใส่ "{ch.id}"
- quote ต้องคัดลอกข้อความจากบทนี้มาตรงตัวอักษร ห้ามแต่งขึ้นใหม่
- suggestion ให้เสนอถ้อยคำที่แก้ไขแล้ว"""


def _ask_judge(ctx: CheckContext, ch: DraftChapter, prompt: str) -> Optional[JudgeResult]:
    """Normalize both answer formats (open-ended / per-item checklist) to JudgeResult."""
    if not ctx.rule.params.get("checklist"):
        return call_structured(prompt, JudgeResult, llm=ctx.llm)
    res = call_structured(prompt, ChecklistResult, llm=ctx.llm)
    if res is None:
        return None
    return JudgeResult(violations=[
        Violation(chapter_id=ch.id, quote=a.quote, reason=a.reason or f"เข้าข่ายรายการตรวจข้อ {a.item}",
                  suggestion=a.suggestion)
        for a in res.answers if a.violated
    ])


def _judge_chapter(ctx: CheckContext, ch: DraftChapter) -> List[Finding]:
    legal = ctx.citation.text if ctx.citation and ctx.citation.text else "(ไม่พบตัวบท)"
    text = ch.as_plain_text()
    key = stable_hash(ctx.rule.id, ctx.rule.params.get("guidance"), ctx.rule.params.get("checklist"), legal, ctx.req.raw_requirements,
                      ctx.req.project_name, ctx.req.budget, ctx.req.duration_days, ctx.method.value,
                      ch.id, ch.title, text)
    if ctx.judge_cache is not None:
        cached = ctx.judge_cache.get(key)
        if cached is not None:
            return cached

    prompt = f"""คุณเป็นผู้ตรวจสอบความถูกต้องตามกฎหมายของร่างขอบเขตของงาน (TOR) ภาครัฐไทย
ตรวจเฉพาะประเด็นนี้เท่านั้น: {ctx.rule.title}

ตัวบทที่ใช้อ้างอิง ({ctx.rule.citation.get('clause') if ctx.rule.citation else ''}):
\"\"\"{legal}\"\"\"

แนวทางการตรวจ: {ctx.rule.params.get('guidance', '')}

ข้อมูลโครงการ (ใช้ประเมินความได้สัดส่วน):
- ชื่อโครงการ: {ctx.req.project_name}
- วงเงินงบประมาณ: {ctx.req.budget:,.2f} บาท
- ระยะเวลาดำเนินงาน: {ctx.req.duration_days} วัน
- วิธีจัดซื้อจัดจ้าง: {ctx.method.value}

ความต้องการที่หน่วยงานระบุเอง (ข้อกำหนดที่สอดคล้องกับความต้องการนี้ถือว่ามีเหตุผลรองรับ ไม่ใช่การละเมิด เว้นแต่เป็นการระบุยี่ห้อ):
\"\"\"{ctx.req.raw_requirements}\"\"\"

บทที่ต้องตรวจ: [chapter_id={ch.id}] {ch.title}
{text}

{_answer_format(ctx, ch)}"""
    result = _ask_judge(ctx, ch, prompt)
    if result is None:  # not cached: a transient failure should be retried next time
        return [ctx.finding(FindingStatus.NEEDS_HUMAN, "ตัวตรวจ LLM ไม่ตอบกลับ ต้องให้เจ้าหน้าที่ตรวจเอง",
                            chapter_id=ch.id)]

    squashed = _squash(text)
    out, ungrounded = [], 0
    for v in result.violations:
        # Grounding guard: discard violations whose quote is not actually in this chapter.
        if _squash(v.quote) not in squashed:
            ungrounded += 1
            continue
        out.append(ctx.finding(FindingStatus.FAIL, v.reason, chapter_id=ch.id,
                               evidence=v.quote, suggestion=v.suggestion))
    if ungrounded and not out:
        out = [ctx.finding(FindingStatus.NEEDS_HUMAN,
                           f"ตัวตรวจ LLM รายงาน {ungrounded} ประเด็นแต่อ้างข้อความที่ไม่มีในร่าง ควรให้คนตรวจซ้ำ",
                           chapter_id=ch.id)]
    out = out or [ctx.finding(FindingStatus.PASS, "ผ่าน", chapter_id=ch.id)]
    if ctx.judge_cache is not None:
        ctx.judge_cache.put(key, out)
    return out


def _snippet(text: str, phrase: str, width: int = 60) -> str:
    i = text.lower().find(phrase.lower())
    return text[max(i - width, 0): i + len(phrase) + width] if i >= 0 else ""


# ----------------- runner -----------------
def _run_rule(rule: Rule, req, method, chapters, facts, index, llm, judge_cache) -> List[Finding]:
    ctx = CheckContext(req, method, chapters, facts, rule, index, llm, judge_cache)
    try:
        return CHECKS[rule.check](ctx)
    except Exception as e:  # a broken check must surface, not pass silently
        return [ctx.finding(FindingStatus.NEEDS_HUMAN, f"ตัวตรวจทำงานผิดพลาด: {e}")]


def run_compliance(
    req: TORRequest,
    method: ProcurementMethod,
    chapters: List[DraftChapter],
    facts: TORFacts,
    index: RegulationIndex,
    llm: Optional[LLMFn] = None,
    registry: Optional[RuleRegistry] = None,
    judge_cache: Optional[JudgeCache] = None,
) -> List[Finding]:
    """Run all applicable rules (in parallel). Findings keep registry order."""
    registry = registry or load_rules()
    rules = [r for r in registry.rules if r.applies(req.procurement_type, method)]
    results = pmap(lambda r: _run_rule(r, req, method, chapters, facts, index, llm, judge_cache), rules)
    return [f for fs in results for f in fs]


def verify(
    req: TORRequest,
    method: ProcurementMethod,
    chapters: List[DraftChapter],
    index: RegulationIndex,
    llm: Optional[LLMFn] = None,
    judge_cache: Optional[JudgeCache] = None,
) -> Tuple[TORFacts, List[Finding]]:
    """Fact extraction and LLM-judge rules don't depend on each other: run them concurrently,
    then run the fact-based rules once facts are in."""
    from app.tor.drafting import extract_facts

    registry = load_rules()
    rules = [r for r in registry.rules if r.applies(req.procurement_type, method)]
    judge_rules = [r for r in rules if r.check == "llm_judge"]

    with ThreadPoolExecutor(max_workers=2) as ex:
        facts_f = ex.submit(extract_facts, chapters, llm)
        judge_f = ex.submit(pmap, lambda r: _run_rule(r, req, method, chapters, None, index, llm, judge_cache),
                            judge_rules)
        facts = facts_f.result()
        judged = dict(zip((r.id for r in judge_rules), judge_f.result()))

    other = [r for r in rules if r.check != "llm_judge"]
    rest = dict(zip((r.id for r in other),
                    pmap(lambda r: _run_rule(r, req, method, chapters, facts, index, llm, judge_cache), other)))
    findings = [f for r in rules for f in (judged.get(r.id) or rest.get(r.id) or [])]
    return facts, findings
