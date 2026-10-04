"""TOR draft -> verify -> revise LangGraph.

    resolve_method -> draft_chapters -> verify --(blocking & budget left)--> revise --+
                                          ^                                           |
                                          +-------------------------------------------+
                                        verify --(else)--> finalize -> END

Chapters are drafted/revised in parallel; verify runs fact extraction concurrently with the
LLM judges. Total in-flight LLM requests are capped by TOR_LLM_CONCURRENCY (app/tor/concurrency.py).
"""
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.config import settings
from app.tor.checks import load_rules, verify
from app.tor.concurrency import JudgeCache, pmap
from app.tor.drafting import draft_chapter
from app.tor.llm import LLMFn
from app.tor.procurement import resolve_method
from app.tor.regulations import RegulationIndex, get_regulation_index
from app.tor.schemas import (
    ComplianceReport, DraftChapter, Finding, FindingStatus, ProcurementMethod, Severity,
    TORFacts, TORRequest, TORResult,
)


class TORState(TypedDict, total=False):
    request: TORRequest
    method: ProcurementMethod
    assumptions: List[str]
    chapters: List[DraftChapter]
    facts: TORFacts
    findings: List[Finding]
    revisions: int
    result: TORResult


def _blocking(findings: List[Finding]) -> List[Finding]:
    return [f for f in findings
            if f.status == FindingStatus.FAIL and f.severity in (Severity.CRITICAL, Severity.MAJOR)]


def _route_to_chapters(findings: List[Finding], chapters: List[DraftChapter]) -> Dict[str, List[Finding]]:
    """Map each blocking finding to the chapter(s) that should be redrafted.

    Fact-level findings (e.g. penalty rate) carry no chapter_id; send them to the chapter whose
    text mentions the rule's revise_keywords.
    """
    rules = {r.id: r for r in load_rules().rules}
    routed: Dict[str, List[Finding]] = {}
    for f in findings:
        targets = [f.chapter_id] if f.chapter_id else [
            c.id for c in chapters
            if any(k in c.as_plain_text() for k in rules[f.rule_id].params.get("revise_keywords", []))
        ]
        for cid in targets:
            routed.setdefault(cid, []).append(f)
    return routed


def build_tor_compliance_graph(
    llm: Optional[LLMFn] = None,
    index: Optional[RegulationIndex] = None,
    max_revisions: Optional[int] = None,
):
    index = index or get_regulation_index()
    max_rev = settings.TOR_MAX_REVISIONS if max_revisions is None else max_revisions
    judge_cache = JudgeCache()  # unchanged chapters are not re-judged across revision rounds

    def resolve_method_node(state: TORState) -> TORState:
        method, assumptions = resolve_method(state["request"])
        return {"method": method, "assumptions": assumptions, "revisions": 0}

    def draft_chapters_node(state: TORState) -> TORState:
        req = state["request"]
        return {"chapters": pmap(lambda spec: draft_chapter(req, state["method"], spec, index, llm),
                                 req.template.chapters)}

    def verify_node(state: TORState) -> TORState:
        facts, findings = verify(state["request"], state["method"], state["chapters"], index, llm, judge_cache)
        return {"facts": facts, "findings": findings}

    def route_after_check(state: TORState) -> str:
        blocking = _blocking(state["findings"])
        if blocking and state["revisions"] < max_rev and _route_to_chapters(blocking, state["chapters"]):
            return "revise"
        return "finalize"

    def revise_node(state: TORState) -> TORState:
        req = state["request"]
        specs = {s.id: s for s in req.template.chapters}
        routed = _route_to_chapters(_blocking(state["findings"]), state["chapters"])
        chapters = pmap(
            lambda c: draft_chapter(req, state["method"], specs[c.id], index, llm, feedback=routed[c.id], previous=c)
            if c.id in routed else c,
            state["chapters"],
        )
        return {"chapters": chapters, "revisions": state["revisions"] + 1}

    def finalize_node(state: TORState) -> TORState:
        report = ComplianceReport(
            rules_version=load_rules().version,
            procurement_type=state["request"].procurement_type,
            procurement_method=state["method"],
            assumptions=state["assumptions"],
            revisions=state["revisions"],
            findings=state["findings"],
        )
        return {"result": TORResult(request=state["request"], chapters=state["chapters"],
                                    facts=state["facts"], report=report)}

    g = StateGraph(TORState)
    g.add_node("resolve_method", resolve_method_node)
    g.add_node("draft_chapters", draft_chapters_node)
    g.add_node("verify", verify_node)
    g.add_node("revise", revise_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("resolve_method")
    g.add_edge("resolve_method", "draft_chapters")
    g.add_edge("draft_chapters", "verify")
    g.add_conditional_edges("verify", route_after_check,
                            {"revise": "revise", "finalize": "finalize"})
    g.add_edge("revise", "verify")
    g.add_edge("finalize", END)
    return g.compile()


def draft_and_verify_tor(request: TORRequest, llm: Optional[LLMFn] = None, actor: str = "system") -> TORResult:
    """Entry point for the super-orchestrator."""
    from app.tor.service import AuditLog, _findings_digest
    graph = build_tor_compliance_graph(llm=llm)
    result = graph.invoke({"request": request})["result"]
    AuditLog().append(result.document_id, "generated", actor, result.version,
                      revisions=result.report.revisions, findings=_findings_digest(result.report.findings))
    return result
