from typing import TypedDict, List, Dict, Any, Optional

class TORGraphState(TypedDict):
    # User Inputs
    project_name: str
    agency_name: str
    budget: float
    duration_days: int
    raw_requirements: str
    
    # Internal Pipeline Progress
    sections_to_draft: List[str]
    current_section_index: int
    
    # Extracted & Drafted Outputs
    drafted_sections: Dict[str, Any]
    output_docx_path: Optional[str]
    errors: List[str]
