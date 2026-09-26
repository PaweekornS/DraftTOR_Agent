from langgraph.graph import StateGraph, END
from app.graphs.state import TORGraphState
from app.graphs.nodes import (
    extract_and_plan_node,
    draft_section_worker_node,
    bureaucratic_polisher_node,
    render_docx_node,
    ALL_SECTIONS
)

def should_continue_drafting(state: TORGraphState) -> str:
    """Conditional router: loop section drafting until all sections are done."""
    idx = state.get("current_section_index", 0)
    total = len(state.get("sections_to_draft", ALL_SECTIONS))
    if idx < total:
        return "draft_section_worker"
    return "bureaucratic_polisher"

def build_tor_graph():
    """Builds and compiles the TOR drafting LangGraph state machine."""
    workflow = StateGraph(TORGraphState)

    # Add Nodes
    workflow.add_node("extract_and_plan", extract_and_plan_node)
    workflow.add_node("draft_section_worker", draft_section_worker_node)
    workflow.add_node("bureaucratic_polisher", bureaucratic_polisher_node)
    workflow.add_node("render_docx_node", render_docx_node)

    # Set Entry Point
    workflow.set_entry_point("extract_and_plan")

    # Connect Edges
    workflow.add_edge("extract_and_plan", "draft_section_worker")
    
    workflow.add_conditional_edges(
        "draft_section_worker",
        should_continue_drafting,
        {
            "draft_section_worker": "draft_section_worker",
            "bureaucratic_polisher": "bureaucratic_polisher"
        }
    )
    
    workflow.add_edge("bureaucratic_polisher", "render_docx_node")
    workflow.add_edge("render_docx_node", END)

    return workflow.compile()

tor_graph = build_tor_graph()
