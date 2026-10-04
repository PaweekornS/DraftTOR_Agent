"""Post-generation operations on an existing TOR: AI chapter revision, manual edits,
re-verification, acknowledgement of findings, and the export gate. Every mutation is audited.

Policy: user-directed changes are never auto-"corrected". The pipeline re-checks and reports;
the user decides, and acknowledging a blocking finding is recorded with actor and reason.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.tor.checks import verify
from app.tor.concurrency import JudgeCache
from app.tor.drafting import draft_chapter
from app.tor.llm import LLMFn
from app.tor.regulations import RegulationIndex, get_regulation_index
from app.tor.schemas import Acknowledgement, DraftChapter, Finding, TORResult


# Shared across rechecks of the production LLM so editing one chapter re-judges only that chapter.
# Custom/stub LLMs get no shared cache, keeping their verdicts isolated.
_JUDGE_CACHE = JudgeCache()


class AuditLog:
    """Append-only JSONL per document. Swap for a DB table in the SaaS backend."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or settings.TOR_AUDIT_DIR)

    def append(self, document_id: str, event: str, actor: str, version: int, **data: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        record = {"at": datetime.now(timezone.utc).isoformat(), "document_id": document_id,
                  "version": version, "event": event, "actor": actor, **data}
        with open(self.root / f"{document_id}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def read(self, document_id: str) -> List[Dict[str, Any]]:
        p = self.root / f"{document_id}.jsonl"
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line]


def _findings_digest(findings: List[Finding]) -> Dict[str, Any]:
    return {"blocking": [f.key for f in findings if f.status.value == "fail" and f.severity.value != "minor"],
            "statuses": {f.key: f.status.value for f in findings}}


def recheck(
    result: TORResult,
    chapters: List[DraftChapter],
    llm: Optional[LLMFn] = None,
    index: Optional[RegulationIndex] = None,
) -> TORResult:
    """Re-extract facts and re-run every rule on the whole document (rules span chapters).

    Acknowledgements survive only for findings that still exist with the same key.
    """
    index = index or get_regulation_index()
    facts, findings = verify(result.request, result.report.procurement_method, chapters, index, llm,
                             judge_cache=_JUDGE_CACHE if llm is None else None)
    live = {f.key for f in findings}
    report = result.report.model_copy(update={
        "findings": findings,
        "acknowledgements": [a for a in result.report.acknowledgements if a.finding_key in live],
    })
    return result.model_copy(update={"chapters": chapters, "facts": facts, "report": report,
                                     "version": result.version + 1})


def revise_chapter(
    result: TORResult,
    chapter_id: str,
    instruction: str,
    actor: str,
    llm: Optional[LLMFn] = None,
    audit: Optional[AuditLog] = None,
) -> TORResult:
    """AI-assisted edit of one chapter following a free-text user instruction. Other chapters untouched."""
    spec = next((s for s in result.request.template.chapters if s.id == chapter_id), None)
    if spec is None:
        raise KeyError(f"Unknown chapter_id: {chapter_id}")
    index = get_regulation_index()
    current = next(c for c in result.chapters if c.id == chapter_id)
    new_ch = draft_chapter(result.request, result.report.procurement_method, spec, index, llm,
                           previous=current, instruction=instruction)
    chapters = [new_ch if c.id == chapter_id else c for c in result.chapters]
    out = recheck(result, chapters, llm, index)
    (audit or AuditLog()).append(out.document_id, "ai_revision", actor, out.version,
                                 chapter_id=chapter_id, instruction=instruction,
                                 before=current.model_dump(), after=new_ch.model_dump(),
                                 findings=_findings_digest(out.report.findings))
    return out


def apply_user_edit(
    result: TORResult,
    chapter: DraftChapter,
    actor: str,
    llm: Optional[LLMFn] = None,
    audit: Optional[AuditLog] = None,
) -> TORResult:
    """Manual edit from the web editor: replace the chapter as-is, then re-verify (advisory)."""
    current = next((c for c in result.chapters if c.id == chapter.id), None)
    if current is None:
        raise KeyError(f"Unknown chapter_id: {chapter.id}")
    chapter = chapter.model_copy(update={"used_fallback": False})  # human-authored now
    chapters = [chapter if c.id == chapter.id else c for c in result.chapters]
    out = recheck(result, chapters, llm)
    (audit or AuditLog()).append(out.document_id, "user_edit", actor, out.version,
                                 chapter_id=chapter.id, before=current.model_dump(), after=chapter.model_dump(),
                                 findings=_findings_digest(out.report.findings))
    return out


def acknowledge(
    result: TORResult,
    finding_keys: List[str],
    actor: str,
    reason: str,
    audit: Optional[AuditLog] = None,
) -> TORResult:
    """User accepts responsibility for specific blocking findings so the document can be exported."""
    if not reason.strip():
        raise ValueError("ต้องระบุเหตุผลในการยืนยันข้ามข้อที่ไม่ผ่าน")
    live = {f.key for f in result.report.findings}
    unknown = [k for k in finding_keys if k not in live]
    if unknown:
        raise KeyError(f"Unknown finding keys: {unknown}")
    now = datetime.now(timezone.utc)
    acks = result.report.acknowledgements + [
        Acknowledgement(finding_key=k, actor=actor, reason=reason, at=now) for k in finding_keys
    ]
    out = result.model_copy(update={"report": result.report.model_copy(update={"acknowledgements": acks})})
    (audit or AuditLog()).append(out.document_id, "acknowledge", actor, out.version,
                                 finding_keys=finding_keys, reason=reason)
    return out


def export_gate(result: TORResult) -> List[Finding]:
    """Blocking findings the user has not acknowledged. Empty list = OK to export."""
    return result.report.unacknowledged_blocking
