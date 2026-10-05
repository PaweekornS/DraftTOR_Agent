"""Web-facing contract: what the editor receives for a TOR document.

The editor works on structured chapters, not HTML/Markdown, so edits round-trip back to
apply_user_edit() and findings can be highlighted via their anchors. TORResult stays internal;
this view drops the raw request and internal facts and adds what the UI needs (summary,
export readiness). Bump SCHEMA_VERSION on any breaking change to these models.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.tor.procurement import METHOD_LABEL_TH, TYPE_LABEL_TH
from app.tor.schemas import (
    Acknowledgement, Anchor, Citation, DraftChapter, FindingStatus, ProcurementMethod, ProcurementType,
    Severity, TORResult,
)

SCHEMA_VERSION = "1.0"


class ProjectSummary(BaseModel):
    project_name: str
    agency_name: str
    budget: float
    duration_days: int
    procurement_type: ProcurementType
    procurement_type_label: str
    procurement_method: ProcurementMethod
    procurement_method_label: str


class FindingView(BaseModel):
    key: str = Field(..., description="Stable id (rule_id:chapter_id); pass to acknowledge()")
    rule_id: str
    title: str
    severity: Severity
    status: FindingStatus
    message: str
    chapter_id: Optional[str] = None
    evidence: Optional[str] = None
    anchor: Optional[Anchor] = Field(None, description="Highlight position inside the chapter")
    suggestion: Optional[str] = None
    confidence: Optional[float] = None
    citation: Optional[Citation] = None
    acknowledged: bool = False


class ReportView(BaseModel):
    passed: bool = Field(..., description="No blocking findings (before acknowledgements)")
    export_ready: bool = Field(..., description="Every blocking finding is resolved or acknowledged")
    summary: Dict[str, int] = Field(..., description="Count of findings by status")
    rules_version: str
    revisions: int
    assumptions: List[str]
    findings: List[FindingView] = Field(..., description="Non-pass findings only, most severe first")
    acknowledgements: List[Acknowledgement]


class TORDocumentView(BaseModel):
    schema_version: str = SCHEMA_VERSION
    document_id: str
    version: int
    project: ProjectSummary
    chapters: List[DraftChapter]
    report: ReportView


_SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}
_STATUS_ORDER = {FindingStatus.FAIL: 0, FindingStatus.NEEDS_HUMAN: 1, FindingStatus.WARN: 2}


def to_view(result: TORResult) -> TORDocumentView:
    req, rep = result.request, result.report
    acked = {a.finding_key for a in rep.acknowledgements}
    chapter_order = {c.id: i for i, c in enumerate(result.chapters)}
    findings = sorted(
        (FindingView(**f.model_dump(), key=f.key, acknowledged=f.key in acked)
         for f in rep.findings if f.status != FindingStatus.PASS),
        key=lambda f: (_STATUS_ORDER.get(f.status, 9), _SEVERITY_ORDER[f.severity.value],
                       chapter_order.get(f.chapter_id or "", 99)),
    )
    return TORDocumentView(
        document_id=result.document_id,
        version=result.version,
        project=ProjectSummary(
            project_name=req.project_name, agency_name=req.agency_name, budget=req.budget,
            duration_days=req.duration_days, procurement_type=req.procurement_type,
            procurement_type_label=TYPE_LABEL_TH[req.procurement_type],
            procurement_method=rep.procurement_method,
            procurement_method_label=METHOD_LABEL_TH[rep.procurement_method],
        ),
        chapters=result.chapters,
        report=ReportView(
            passed=rep.passed, export_ready=not rep.unacknowledged_blocking, summary=rep.summary(),
            rules_version=rep.rules_version, revisions=rep.revisions, assumptions=rep.assumptions,
            findings=findings, acknowledgements=rep.acknowledgements,
        ),
    )


def write_json_schema(path: Optional[str] = None) -> Path:
    """Emit the JSON Schema so the frontend can generate TypeScript types."""
    out = Path(path or f"docs/api/tor_document.v{SCHEMA_VERSION}.schema.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(TORDocumentView.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
    return out
