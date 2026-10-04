"""Template-driven chapter drafting and fact extraction."""
import re
from typing import List, Optional

from pydantic import BaseModel, Field

from app.tor.llm import LLMFn, call_structured
from app.tor.procurement import METHOD_LABEL_TH, TYPE_LABEL_TH
from app.tor.regulations import RegulationIndex, normalize
from app.tor.schemas import (
    BOQItem, ChapterKind, DraftChapter, Finding, Installment, ProcurementMethod,
    TemplateChapter, TORFacts, TORRequest,
)

# Contract templates (แบบสัญญา) under ประกาศคกกนโยบาย leaked unrelated clauses into drafts; keep to primary law.
LAW_CATEGORIES = ["พรบ", "ระเบียบกระทรวงการคลัง"]


class TextOut(BaseModel):
    text: str = Field(..., min_length=20)


class ListOut(BaseModel):
    items: List[str] = Field(..., min_length=1)


class BOQLine(BaseModel):
    name: str
    unit: str = "รายการ"
    weight_pct: float = Field(..., gt=0)


class BOQOut(BaseModel):
    items: List[BOQLine] = Field(..., min_length=1)


class PaymentOut(BaseModel):
    installments: List[Installment] = Field(..., min_length=1)


OUTPUT_MODEL = {
    ChapterKind.TEXT: TextOut,
    ChapterKind.LIST: ListOut,
    ChapterKind.BOQ: BOQOut,
    ChapterKind.PAYMENT_SCHEDULE: PaymentOut,
}

KIND_INSTRUCTION = {
    ChapterKind.TEXT: "เขียนเป็นความเรียงภาษาราชการ ไม่ต้องใส่หัวข้อหรือเลขข้อ",
    ChapterKind.LIST: "เขียนเป็นรายการข้อ ๆ แต่ละข้อเป็นประโยคสมบูรณ์ ไม่ต้องใส่เลขข้อ",
    ChapterKind.BOQ: "แจกแจงหมวดค่าใช้จ่าย 3-6 รายการ พร้อมสัดส่วนร้อยละ (weight_pct) ระบบจะคำนวณจำนวนเงินเอง ห้ามใส่ตัวเลขเงิน",
    ChapterKind.PAYMENT_SCHEDULE: "แบ่งงวดงาน ระบุร้อยละการจ่าย สิ่งส่งมอบ และวันครบกำหนด ร้อยละรวมต้องเท่ากับ 100 พอดี และวันครบกำหนดงวดสุดท้ายต้องไม่เกินระยะเวลาดำเนินงาน",
}


def _context_block(req: TORRequest, method: ProcurementMethod) -> str:
    return f"""ข้อมูลโครงการ:
- ชื่อโครงการ: {req.project_name}
- หน่วยงาน: {req.agency_name}
- ประเภท: {TYPE_LABEL_TH[req.procurement_type]}
- วิธีจัดซื้อจัดจ้าง: {METHOD_LABEL_TH[method]}
- วงเงินงบประมาณ: {req.budget:,.2f} บาท
- ระยะเวลาดำเนินงาน: {req.duration_days} วัน
- ความต้องการ: {req.raw_requirements}"""


def draft_chapter(
    req: TORRequest,
    method: ProcurementMethod,
    spec: TemplateChapter,
    index: RegulationIndex,
    llm: Optional[LLMFn] = None,
    feedback: Optional[List[Finding]] = None,
    previous: Optional[DraftChapter] = None,
    instruction: Optional[str] = None,
) -> DraftChapter:
    refs = index.search(f"{spec.title} {spec.instructions} {instruction or ''}", k=3, categories=LAW_CATEGORIES)
    ref_block = "\n\n".join(f"[{c.ref}]\n{c.text[:800]}" for c in refs)

    revise_block = ""
    if instruction:
        # User-directed edit: follow the user. Compliance is reported afterwards, not enforced here.
        revise_block = f"""
ร่างปัจจุบันของบทนี้:
\"\"\"{previous.as_plain_text() if previous else ''}\"\"\"

คำสั่งแก้ไขจากผู้ใช้ (ต้องทำตาม และคงเนื้อหาส่วนที่ผู้ใช้ไม่ได้สั่งให้เปลี่ยนไว้):
{instruction}
"""
    elif feedback:
        issues = "\n".join(
            f"- [{f.rule_id}] {f.message}" + (f" | ข้อความ: \"{f.evidence}\"" if f.evidence else "")
            + (f" | แนะนำ: {f.suggestion}" if f.suggestion else "")
            for f in feedback
        )
        revise_block = f"""
ร่างเดิมของบทนี้:
\"\"\"{previous.as_plain_text() if previous else ''}\"\"\"

ร่างเดิมไม่ผ่านการตรวจสอบระเบียบในประเด็นต่อไปนี้ ต้องแก้ไขให้ครบทุกข้อ:
{issues}
"""

    # A user's explicit instruction overrides drafting policy; the checker reports the consequences.
    no_fake_citations = "- ห้ามแต่งเลขมาตราหรือข้อระเบียบที่ไม่ปรากฏในตัวบทอ้างอิงด้านล่าง"
    if instruction:
        constraints = f"ข้อห้าม:\n{no_fake_citations}"
    else:
        constraints = f"""ข้อห้าม:
- ห้ามระบุยี่ห้อ รุ่น หรือชื่อบริษัท ให้ใช้คุณลักษณะเชิงหน้าที่และ "หรือเทียบเท่า"
- ใช้ถ้อยคำที่สอดคล้องกับ{METHOD_LABEL_TH[method]}เท่านั้น
{no_fake_citations}"""

    prompt = f"""คุณเป็นเจ้าหน้าที่พัสดุผู้เชี่ยวชาญการจัดทำร่างขอบเขตของงาน (TOR) ตาม พ.ร.บ.การจัดซื้อจัดจ้างฯ พ.ศ. ๒๕๖๐
{_context_block(req, method)}

บทที่ต้องร่าง: {spec.title}
ข้อกำหนดของบทนี้จากแม่แบบ: {spec.instructions or '-'}
รูปแบบ: {KIND_INSTRUCTION[spec.kind]}

{constraints}

ตัวบทกฎหมายที่อาจเกี่ยวข้อง (ใช้เพื่อให้เนื้อหาถูกต้องตามระเบียบเท่านั้น ห้ามคัดลอกข้อความหรือรายการที่ไม่เกี่ยวกับโครงการนี้):
{ref_block}
{revise_block}"""

    out = call_structured(prompt, OUTPUT_MODEL[spec.kind], llm=llm)
    ch = DraftChapter(id=spec.id, title=spec.title, kind=spec.kind)
    if out is None:
        return _fallback(ch, req)
    if spec.kind == ChapterKind.TEXT:
        ch.text = out.text.strip()
    elif spec.kind == ChapterKind.LIST:
        ch.items = [i.strip() for i in out.items if i.strip()]
    elif spec.kind == ChapterKind.BOQ:
        ch.boq = allocate_budget(req.budget, out.items)
    else:
        ch.installments = sorted(out.installments, key=lambda i: i.no)
    return ch


def allocate_budget(budget: float, lines: List[BOQLine]) -> List[BOQItem]:
    """LLM proposes categories+weights; Python owns the money. Last line absorbs rounding."""
    total_w = sum(l.weight_pct for l in lines)
    items, allocated = [], 0.0
    for i, line in enumerate(lines):
        amount = round(budget - allocated, 2) if i == len(lines) - 1 else round(budget * line.weight_pct / total_w, 2)
        allocated = round(allocated + amount, 2)
        items.append(BOQItem(name=line.name, unit=line.unit, qty=1, unit_price=amount, total_price=amount))
    return items


def _fallback(ch: DraftChapter, req: TORRequest) -> DraftChapter:
    ch.used_fallback = True
    if ch.kind == ChapterKind.BOQ:
        ch.boq = [BOQItem(name=req.project_name, unit="งาน", unit_price=req.budget, total_price=req.budget)]
    elif ch.kind == ChapterKind.PAYMENT_SCHEDULE:
        ch.installments = [Installment(no=1, percent=100, deliverable="ส่งมอบงานทั้งหมด", due_day=req.duration_days)]
    else:
        ch.text = f"[ต้องร่างเพิ่ม: {ch.title}]"
    return ch


def extract_facts(chapters: List[DraftChapter], llm: Optional[LLMFn] = None) -> TORFacts:
    body = "\n\n".join(f"{c.title}\n{c.as_plain_text()}" for c in chapters)
    prompt = f"""สกัดข้อมูลตัวเลขต่อไปนี้จากร่าง TOR ถ้าเอกสารไม่ได้ระบุไว้ให้ใส่ null ห้ามเดา
- penalty_rate_pct_per_day: อัตราค่าปรับรายวัน (ร้อยละต่อวัน)
- performance_bond_pct: หลักประกันสัญญา (ร้อยละ)
- bid_bond_pct: หลักประกันการเสนอราคา (ร้อยละ)
- min_reference_work_value: มูลค่าผลงานอ้างอิงขั้นต่ำที่กำหนดให้ผู้ยื่นข้อเสนอ (บาท)
- allows_subcontracting: อนุญาตให้จ้างช่วงหรือไม่
- subcontract_penalty_pct: ค่าปรับกรณีจ้างช่วงโดยไม่ได้รับอนุญาต (ร้อยละของวงเงินที่จ้างช่วง)

ร่าง TOR:
{body}"""
    llm_facts = call_structured(prompt, TORFacts, llm=llm)
    rx = _regex_facts(body)
    if llm_facts is None:
        return rx.model_copy(update={"extraction_ok": False})
    # Regex fills gaps the LLM left null; it never overrides an LLM value.
    filled = {k: v for k, v in rx.model_dump(exclude={"extraction_ok"}).items()
              if v is not None and getattr(llm_facts, k) is None}
    return llm_facts.model_copy(update=filled)


_NUM = r"([0-9]+(?:\.[0-9]+)?)"
_GAP = r"[^\n]{0,%d}?"
_FACT_PATTERNS = {
    "penalty_rate_pct_per_day": [
        "ค่าปรับ" + _GAP % 60 + "(?:รายวัน|ต่อวัน|วันละ)" + _GAP % 40 + r"ร้อยละ\s*" + _NUM,
        "ค่าปรับ" + _GAP % 60 + r"ร้อยละ\s*" + _NUM + _GAP % 10 + "(?:ต่อวัน|รายวัน)",
    ],
    "performance_bond_pct": ["หลักประกันสัญญา" + _GAP % 20 + r"ร้อยละ\s*" + _NUM],
    "bid_bond_pct": ["หลักประกันการเสนอราคา" + _GAP % 20 + r"ร้อยละ\s*" + _NUM],
    "subcontract_penalty_pct": ["จ้างช่วง" + _GAP % 120 + "ค่าปรับ" + _GAP % 10 + r"ร้อยละ\s*" + _NUM],
    "min_reference_work_value": ["ผลงาน" + _GAP % 80 + r"วงเงิน" + _GAP % 20 + r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*บาท"],
}


def _regex_facts(text: str) -> TORFacts:
    """Cheap deterministic backstop for the LLM extractor (Thai digits normalized first)."""
    t = normalize(text)
    found = {}
    for name, pats in _FACT_PATTERNS.items():
        for pat in pats:
            m = re.search(pat, t)
            if m:
                found[name] = float(m.group(1).replace(",", ""))
                break
    return TORFacts(**found)
