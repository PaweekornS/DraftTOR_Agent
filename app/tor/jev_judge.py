"""Semantic-rule judging with the Jev decision model (TOR_JUDGE_BACKEND=jev).

Jev returns a choice with softmax probabilities but no quote or rewrite, so judging is done per
unit (one list item or one sentence). The unit is the evidence, so it is grounded by construction.
All units of all in-scope chapters go out in batched requests; verdicts are cached per unit.

Status from P(violation):  >= jev_fail_threshold -> FAIL;  >= jev_review_threshold -> NEEDS_HUMAN.
"""
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from app.config import settings
from app.services import jev_client
from app.tor.concurrency import limited, pmap, stable_hash
from app.tor.schemas import DraftChapter, Finding, FindingStatus

if TYPE_CHECKING:
    from app.tor.checks import CheckContext

COMPLIANT = "compliant"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\s{2,}|\n+")


def split_units(ch: DraftChapter, min_len: int = 40) -> List[str]:
    """List items as-is; prose split into sentences, merging fragments shorter than min_len."""
    if ch.items:
        return [i.strip() for i in ch.items if i.strip()]
    units: List[str] = []
    for piece in _SENTENCE_SPLIT.split(ch.as_plain_text()):
        piece = piece.strip()
        if not piece:
            continue
        if units and len(units[-1]) < min_len:
            units[-1] = f"{units[-1]} {piece}"
        else:
            units.append(piece)
    return units


def _criteria(ctx: "CheckContext") -> Dict[str, str]:
    checklist = ctx.rule.params.get("checklist")
    if checklist:
        crit = {f"item_{i}": c for i, c in enumerate(checklist, 1)}
        crit[COMPLIANT] = "ไม่เข้าข่ายรายการใดเลย"
        return crit
    return {"violation": ctx.rule.title, COMPLIANT: "ไม่เข้าข่าย หรือมีเหตุผลรองรับตามแนวทางการตรวจ"}


def _state(ctx: "CheckContext") -> Dict[str, Any]:
    legal = ctx.citation.text if ctx.citation and ctx.citation.text else ""
    return {
        "task": "ตรวจว่าข้อความในร่างขอบเขตของงาน (TOR) ภาครัฐไทยขัดกับกฎหมายจัดซื้อจัดจ้างหรือไม่",
        "rule": ctx.rule.title,
        "legal_text": legal[:3000],
        "guidance": ctx.rule.params.get("guidance", ""),
        "agency_requirements": ctx.req.raw_requirements,
        "project": {"name": ctx.req.project_name, "budget_baht": ctx.req.budget,
                    "duration_days": ctx.req.duration_days, "procurement_method": ctx.method.value},
    }


def _cache_key(ctx: "CheckContext", state: Dict[str, Any], criteria: Dict[str, str], unit: str) -> str:
    return stable_hash("jev", settings.JEV_MODEL_NAME, ctx.rule.id, state, criteria, unit)


def jev_judge_chapters(ctx: "CheckContext", chapters: List[DraftChapter],
                       decide: Optional[jev_client.DecideFn] = None) -> List[Finding]:
    decide = limited(decide or jev_client.decide)
    fail_t = float(ctx.rule.params.get("jev_fail_threshold", 0.7))
    review_t = float(ctx.rule.params.get("jev_review_threshold", 0.4))
    state, criteria = _state(ctx), _criteria(ctx)

    units: List[Tuple[DraftChapter, str]] = [(ch, u) for ch in chapters for u in split_units(ch)]
    verdicts: Dict[int, Optional[Dict[str, Any]]] = {}
    pending: List[int] = []
    for i, (_, u) in enumerate(units):
        cached = ctx.judge_cache.get(_cache_key(ctx, state, criteria, u)) if ctx.judge_cache else None
        if cached is not None:
            verdicts[i] = cached
        else:
            pending.append(i)

    size = settings.JEV_MAX_QUESTIONS_PER_REQUEST
    batches = [pending[k:k + size] for k in range(0, len(pending), size)]

    def ask(batch: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
        questions = {
            f"u{i}": {"type": "choice", "criteria": criteria,
                      "instructions": f"ข้อความจากบท '{units[i][0].title}':\n\"{units[i][1]}\"\n"
                                      f"ข้อความนี้เข้าข่ายข้อใด"}
            for i in batch
        }
        try:
            answers = decide(state, questions)
        except Exception:
            return {i: None for i in batch}
        return {i: answers.get(f"u{i}") for i in batch}

    for result in pmap(ask, batches):
        for i, ans in result.items():
            verdicts[i] = ans
            if ans is not None and ctx.judge_cache is not None:
                ctx.judge_cache.put(_cache_key(ctx, state, criteria, units[i][1]), ans)

    findings: List[Finding] = []
    for i, (ch, unit) in enumerate(units):
        ans = verdicts.get(i)
        if not ans or "probabilities" not in ans:
            findings.append(ctx.finding(FindingStatus.NEEDS_HUMAN, "ตัวตัดสิน Jev ไม่ตอบกลับ ต้องให้เจ้าหน้าที่ตรวจเอง",
                                        chapter_id=ch.id, evidence=unit))
            continue
        probs: Dict[str, float] = ans["probabilities"]
        p_violation = round(1.0 - float(probs.get(COMPLIANT, 0.0)), 4)
        if p_violation < review_t:
            continue
        top = max((k for k in probs if k != COMPLIANT), key=lambda k: probs[k], default="violation")
        reason = criteria.get(top, ctx.rule.title)
        status = FindingStatus.FAIL if p_violation >= fail_t else FindingStatus.NEEDS_HUMAN
        prefix = "" if status == FindingStatus.FAIL else "[ไม่แน่ใจ ควรให้คนตรวจ] "
        findings.append(ctx.finding(status, f"{prefix}{reason} (ความน่าจะเป็น {p_violation:.2f})",
                                    chapter_id=ch.id, evidence=unit,
                                    suggestion=ctx.rule.params.get("suggestion"),
                                    confidence=p_violation))
    return findings
