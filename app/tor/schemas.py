"""Contracts between the super-orchestrator and the TOR draft+compliance pipeline."""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4
from pydantic import BaseModel, Field


class ProcurementType(str, Enum):
    GOODS = "goods"                            # ซื้อ
    SERVICES = "services"                      # จ้างทั่วไป (ไม่ใช่ก่อสร้าง/ที่ปรึกษา)
    CONSULTING = "consulting"                  # จ้างที่ปรึกษา
    DESIGN_SUPERVISION = "design_supervision"  # จ้างออกแบบหรือควบคุมงานก่อสร้าง
    CONSTRUCTION = "construction"              # จ้างก่อสร้าง


class ProcurementMethod(str, Enum):
    E_MARKET = "e_market"                # ตลาดอิเล็กทรอนิกส์
    E_BIDDING = "e_bidding"              # ประกวดราคาอิเล็กทรอนิกส์
    SELECTION = "selection"              # วิธีคัดเลือก
    SPECIFIC = "specific"                # วิธีเฉพาะเจาะจง
    GENERAL_INVITATION = "general_invitation"  # ประกาศเชิญชวนทั่วไป (จ้างที่ปรึกษา)


class ChapterKind(str, Enum):
    TEXT = "text"                    # ความเรียง
    LIST = "list"                    # รายการข้อ ๆ
    BOQ = "boq"                      # ตารางแจกแจงงบประมาณ
    PAYMENT_SCHEDULE = "payment_schedule"  # งวดงานและการจ่ายเงิน


# ----------------- Input from super-orchestrator -----------------
class TemplateChapter(BaseModel):
    id: str = Field(..., description="รหัสบท เช่น 'scope_of_work'")
    title: str = Field(..., description="ชื่อบทตามแม่แบบ เช่น 'ขอบเขตของงาน'")
    kind: ChapterKind = ChapterKind.TEXT
    instructions: str = Field("", description="คำอธิบาย/ข้อกำหนดเนื้อหาของบทนี้จากแม่แบบ")
    required: bool = True


class TORTemplateSpec(BaseModel):
    template_id: str
    chapters: List[TemplateChapter]


class TORRequest(BaseModel):
    project_name: str
    agency_name: str
    budget: float = Field(..., gt=0)
    duration_days: int = Field(..., gt=0)
    raw_requirements: str
    procurement_type: ProcurementType
    procurement_method: Optional[ProcurementMethod] = Field(
        None, description="ถ้า upstream กำหนดมาแล้วให้ใช้ค่านี้ ไม่เช่นนั้นระบบจะจำแนกเอง"
    )
    template: TORTemplateSpec
    extra_context: Dict[str, Any] = Field(default_factory=dict)


# ----------------- Draft artifacts -----------------
class BOQItem(BaseModel):
    name: str
    qty: int = 1
    unit: str = "รายการ"
    unit_price: float
    total_price: float


class Installment(BaseModel):
    no: int
    percent: float
    deliverable: str
    due_day: int = Field(..., description="ภายในวันที่เท่าใดนับจากวันลงนามสัญญา")


class DraftChapter(BaseModel):
    id: str
    title: str
    kind: ChapterKind
    text: str = ""
    items: List[str] = Field(default_factory=list)
    boq: List[BOQItem] = Field(default_factory=list)
    installments: List[Installment] = Field(default_factory=list)
    used_fallback: bool = False

    def as_plain_text(self) -> str:
        parts = [self.text] if self.text else []
        parts += [f"- {i}" for i in self.items]
        parts += [f"- {b.name}: {b.total_price:,.2f} บาท" for b in self.boq]
        parts += [
            f"- งวดที่ {i.no} (ร้อยละ {i.percent:g}): {i.deliverable} ภายใน {i.due_day} วัน"
            for i in self.installments
        ]
        return "\n".join(parts)


class TORFacts(BaseModel):
    """Numeric/legal facts extracted from the draft so rules can be checked deterministically."""
    penalty_rate_pct_per_day: Optional[float] = None
    performance_bond_pct: Optional[float] = None
    bid_bond_pct: Optional[float] = None
    min_reference_work_value: Optional[float] = None
    allows_subcontracting: Optional[bool] = None
    subcontract_penalty_pct: Optional[float] = None
    extraction_ok: bool = Field(True, description="False when the LLM extractor failed; values are regex-only")


# ----------------- Compliance output -----------------
class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class FindingStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    NEEDS_HUMAN = "needs_human"   # กฎที่ยังไม่ผ่านการยืนยันจากผู้เชี่ยวชาญ หรือ LLM ไม่มั่นใจ


class Citation(BaseModel):
    doc: str
    clause: str
    text: Optional[str] = None


class Anchor(BaseModel):
    """Where a finding's evidence sits inside its chapter (for highlighting in the editor)."""
    item_index: Optional[int] = Field(None, description="Index into DraftChapter.items; None for text chapters")
    start: int = Field(..., description="Start offset within the item (list) or within DraftChapter.text")
    end: int = Field(..., description="End offset (exclusive)")


class Finding(BaseModel):
    rule_id: str
    title: str
    severity: Severity
    status: FindingStatus
    message: str
    chapter_id: Optional[str] = None
    evidence: Optional[str] = None
    suggestion: Optional[str] = None
    citation: Optional[Citation] = None
    confidence: Optional[float] = Field(None, description="Judge probability that this is a violation (Jev backend)")
    anchor: Optional[Anchor] = None

    @property
    def key(self) -> str:
        """Stable identity used to carry user acknowledgements across re-checks."""
        return f"{self.rule_id}:{self.chapter_id or '*'}"


class Acknowledgement(BaseModel):
    finding_key: str
    actor: str
    reason: str
    at: datetime


class ComplianceReport(BaseModel):
    rules_version: str
    procurement_type: ProcurementType
    procurement_method: ProcurementMethod
    assumptions: List[str] = Field(default_factory=list)
    revisions: int = 0
    findings: List[Finding] = Field(default_factory=list)
    acknowledgements: List[Acknowledgement] = Field(default_factory=list)

    @property
    def blocking(self) -> List[Finding]:
        return [f for f in self.findings
                if f.status == FindingStatus.FAIL and f.severity in (Severity.CRITICAL, Severity.MAJOR)]

    @property
    def unacknowledged_blocking(self) -> List[Finding]:
        acked = {a.finding_key for a in self.acknowledgements}
        return [f for f in self.blocking if f.key not in acked]

    @property
    def passed(self) -> bool:
        return not self.blocking

    def summary(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for f in self.findings:
            out[f.status.value] = out.get(f.status.value, 0) + 1
        return out


class TORResult(BaseModel):
    document_id: str = Field(default_factory=lambda: uuid4().hex)
    version: int = 1
    request: TORRequest
    chapters: List[DraftChapter]
    facts: TORFacts
    report: ComplianceReport
