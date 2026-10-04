from typing import Dict, Any, Union
from app.schemas.gov_documents import (
    DocumentType,
    MemoInputRequest,
    MemoDraftPayload,
    MeetingAgendaRequest,
    MeetingAgendaPayload
)
from app.graphs.memo_workflow import draft_memo_document
from app.graphs.agenda_workflow import draft_meeting_agenda_document

class DocumentOrchestrator:
    """
    Memo / Meeting Agenda drafting dispatcher. TOR drafting moved to app.tor (draft_and_verify_tor).
    Dispatches generation tasks according to document type:
    - DocumentType.MEMO: Runs Memo pipeline with Saraban structure + 1.5cm Garuda
    - DocumentType.MEETING_AGENDA: Runs 5-Agenda pipeline with formal committee formatting
    """

    @classmethod
    def draft_document(
        cls,
        doc_type: DocumentType,
        request_data: Union[MemoInputRequest, MeetingAgendaRequest, Dict[str, Any]]
    ) -> Dict[str, Any]:
        
        print(f"\n=======================================================")
        print(f"🏛️ Starting Government Document Generator: [{doc_type.value}]")
        print(f"=======================================================")

        if doc_type == DocumentType.MEMO:
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
