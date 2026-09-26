from typing import Dict, Any, Union
from app.schemas.gov_documents import (
    DocumentType,
    TORInputRequest,
    TORDraftPayload,
    MemoInputRequest,
    MemoDraftPayload,
    MeetingAgendaRequest,
    MeetingAgendaPayload
)
from app.graphs.workflow import tor_graph
from app.graphs.memo_workflow import draft_memo_document
from app.graphs.agenda_workflow import draft_meeting_agenda_document

class DocumentOrchestrator:
    """
    Central Multi-Document Drafting Engine.
    Dispatches generation tasks according to document type:
    - DocumentType.TOR: Runs LangGraph state machine with 7 sections + BOQ table + 3cm Garuda
    - DocumentType.MEMO: Runs Memo pipeline with Saraban structure + 1.5cm Garuda
    - DocumentType.MEETING_AGENDA: Runs 5-Agenda pipeline with formal committee formatting
    """

    @classmethod
    def draft_document(
        cls,
        doc_type: DocumentType,
        request_data: Union[TORInputRequest, MemoInputRequest, MeetingAgendaRequest, Dict[str, Any]]
    ) -> Dict[str, Any]:
        
        print(f"\n=======================================================")
        print(f"🏛️ Starting Government Document Generator: [{doc_type.value}]")
        print(f"=======================================================")

        if doc_type == DocumentType.TOR:
            if isinstance(request_data, dict):
                req = TORInputRequest(**request_data)
            else:
                req = request_data

            initial_state = {
                "project_name": req.project_name,
                "agency_name": req.agency_name,
                "budget": req.budget,
                "duration_days": req.duration_days,
                "raw_requirements": req.raw_requirements,
                "sections_to_draft": [],
                "current_section_index": 0,
                "drafted_sections": {},
                "output_docx_path": None,
                "errors": []
            }
            final_state = tor_graph.invoke(initial_state)
            payload = TORDraftPayload(**final_state["drafted_sections"])
            return {
                "document_type": DocumentType.TOR,
                "payload": payload,
                "output_docx_path": final_state["output_docx_path"]
            }

        elif doc_type == DocumentType.MEMO:
            if isinstance(request_data, dict):
                req = MemoInputRequest(**request_data)
            else:
                req = request_data
            
            result = draft_memo_document(req)
            return {
                "document_type": DocumentType.MEMO,
                "payload": result["payload"],
                "output_docx_path": result["output_docx_path"]
            }

        elif doc_type == DocumentType.MEETING_AGENDA:
            if isinstance(request_data, dict):
                req = MeetingAgendaRequest(**request_data)
            else:
                req = request_data
            
            result = draft_meeting_agenda_document(req)
            return {
                "document_type": DocumentType.MEETING_AGENDA,
                "payload": result["payload"],
                "output_docx_path": result["output_docx_path"]
            }

        else:
            raise ValueError(f"Unsupported document type: {doc_type}")

document_orchestrator = DocumentOrchestrator()
