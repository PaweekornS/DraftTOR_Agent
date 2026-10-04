import os
from docxtpl import DocxTemplate
from app.schemas.gov_documents import MemoDraftPayload, MeetingAgendaPayload
from app.config import settings

def resolve_path(configured_path: str, default_local: str) -> str:
    """Resolves Docker-style paths (/app/...) to local project directory when running locally."""
    if os.path.exists(configured_path):
        return configured_path
    if configured_path.startswith("/app"):
        local_candidate = configured_path.replace("/app/", "").replace("/app", "")
        if os.path.exists(local_candidate):
            return local_candidate
    if os.path.exists(default_local):
        return default_local
    return configured_path

def render_memo_docx(payload: MemoDraftPayload, template_filename: str = "memo_template.docx", output_filename: str = None) -> str:
    """Renders an official Memo (บันทึกข้อความ) with 1.5cm Garuda emblem into .docx."""
    template_dir = resolve_path(settings.TEMPLATE_DIR, "app/templates")
    template_path = os.path.join(template_dir, template_filename)
    
    if not os.path.exists(template_path):
        fallback_path = os.path.join("app", "templates", template_filename)
        if os.path.exists(fallback_path):
            template_path = fallback_path
        else:
            raise FileNotFoundError(f"Template not found at: {template_path}")

    output_dir = resolve_path(settings.OUTPUT_DIR, "data/outputs")
    os.makedirs(output_dir, exist_ok=True)

    if not output_filename:
        safe_subj = "".join([c if c.isalnum() else "_" for c in payload.subject])[:30]
        output_filename = f"memo_draft_{safe_subj}.docx"

    output_path = os.path.join(output_dir, output_filename)
    
    doc = DocxTemplate(template_path)
    context = payload.model_dump()
    doc.render(context)
    doc.save(output_path)
    return output_path

def render_meeting_agenda_docx(payload: MeetingAgendaPayload, template_filename: str = "meeting_agenda_template.docx", output_filename: str = None) -> str:
    """Renders an official 5-Agendas Meeting Agenda document into .docx."""
    template_dir = resolve_path(settings.TEMPLATE_DIR, "app/templates")
    template_path = os.path.join(template_dir, template_filename)
    
    if not os.path.exists(template_path):
        fallback_path = os.path.join("app", "templates", template_filename)
        if os.path.exists(fallback_path):
            template_path = fallback_path
        else:
            raise FileNotFoundError(f"Template not found at: {template_path}")

    output_dir = resolve_path(settings.OUTPUT_DIR, "data/outputs")
    os.makedirs(output_dir, exist_ok=True)

    if not output_filename:
        safe_comm = "".join([c if c.isalnum() else "_" for c in payload.committee_name])[:30]
        output_filename = f"agenda_draft_{safe_comm}_{payload.meeting_no}_{payload.meeting_year}.docx"

    output_path = os.path.join(output_dir, output_filename)
    
    doc = DocxTemplate(template_path)
    context = payload.model_dump()
    doc.render(context)
    doc.save(output_path)
    return output_path
