import re
from typing import Dict, Any, List
from app.schemas.gov_documents import MeetingAgendaRequest, MeetingAgendaPayload
from app.services.llm_factory import call_llm
from app.services.docx_renderer import render_meeting_agenda_docx

def clean_agenda_items(text: str) -> List[str]:
    lines = []
    for line in text.strip().split("\n"):
        cleaned = re.sub(r'^\s*[\d\.\-\*\•\)]+\s*', '', line).strip()
        cleaned = cleaned.strip('"\'[],')
        if cleaned and len(cleaned) > 3 and not cleaned.startswith('{') and not cleaned.startswith('}'):
            lines.append(cleaned)
    return lines

def draft_meeting_agenda_document(req: MeetingAgendaRequest) -> Dict[str, Any]:
    """
    Drafts an official Thai Government 5-Agenda Meeting Document
    (ระเบียบวาระการประชุมคณะกรรมการ/คณะทำงาน).
    Standard Agendas:
    วาระที่ ๑: เรื่องที่ประธานแจ้งให้ที่ประชุมทราบ
    วาระที่ ๒: เรื่องรับรองรายงานการประชุม
    วาระที่ ๓: เรื่องสืบเนื่อง / เพื่อทราบ
    วาระที่ ๔: เรื่องเสนอเพื่อพิจารณา
    วาระที่ ๕: เรื่องอื่นๆ
    """
    print(f"\n[Agenda Pipeline] Drafting meeting agenda for: '{req.committee_name}' ครั้งที่ {req.meeting_no}/{req.meeting_year}...", flush=True)

    prompt = f"""คุณเป็นฝ่ายเลขานุการการประชุมภาครัฐระดับมืออาชีพ
โปรดจัดทำ 'ระเบียบวาระการประชุม' ตามระเบียบแบบแผนทางราชการ สำหรับการประชุม:
- คณะกรรมการ/การประชุม: {req.committee_name}
- ข้อมูลประเด็นที่เสนอเข้าประชุม: {req.raw_agenda_topics}

คำสั่ง:
โปรดแตกประเด็นการประชุมออกเป็น 2 ส่วนสำคัญในรูปแบบภาษาราชการ:
1. ประเด็นเพื่อทราบ (วาระที่ 3): 1-2 ข้อ (เช่น รายงานความคืบหน้า...)
2. ประเด็นเพื่อพิจารณา (วาระที่ 4): 1-3 ข้อ (เช่น พิจารณาให้ความเห็นชอบ...)

รูปแบบผลลัพธ์:
=== วาระเพื่อทราบ ===
- [ข้อความ]
=== วาระเพื่อพิจารณา ===
- [ข้อความ]
"""
    response_text = call_llm([{"role": "user", "content": prompt}])
    
    matters_to_inform = []
    matters_for_consideration = []

    if "=== วาระเพื่อทราบ ===" in response_text and "=== วาระเพื่อพิจารณา ===" in response_text:
        parts = response_text.split("=== วาระเพื่อพิจารณา ===")
        inform_part = parts[0].replace("=== วาระเพื่อทราบ ===", "").strip()
        consider_part = parts[1].strip() if len(parts) > 1 else ""
        
        matters_to_inform = clean_agenda_items(inform_part)
        matters_for_consideration = clean_agenda_items(consider_part)

    if not matters_to_inform:
        matters_to_inform = [
            f"รายงานความก้าวหน้าการดำเนินงานโครงการที่เกี่ยวข้องของ {req.committee_name}",
            "รายงานผลการเบิกจ่ายและการจัดซื้อจัดจ้างตามแผนงบประมาณ"
        ]

    if not matters_for_consideration:
        raw_items = [t.strip() for t in req.raw_agenda_topics.split("\n") if t.strip()]
        matters_for_consideration = [f"พิจารณา{item}" if not item.startswith("พิจารณา") else item for item in raw_items]

    payload = MeetingAgendaPayload(
        committee_name=req.committee_name,
        meeting_no=req.meeting_no,
        meeting_year=req.meeting_year,
        meeting_date=req.meeting_date,
        meeting_time=req.meeting_time,
        meeting_location=req.meeting_location,
        agenda_1_chairman_notes="ประธานแจ้งให้ที่ประชุมทราบถึงเป้าหมายและกรอบแนวทางการดำเนินงานที่สำคัญของหน่วยงาน",
        agenda_2_previous_minutes=f"รับรองรายงานการประชุม {req.committee_name} ครั้งที่ {req.meeting_no - 1 if req.meeting_no > 1 else 1}/{req.meeting_year}",
        agenda_3_matters_to_inform=matters_to_inform,
        agenda_4_matters_for_consideration=matters_for_consideration,
        agenda_5_other_matters="ไม่มี"
    )

    out_docx = render_meeting_agenda_docx(payload)
    print(f"✓ Generated official Agenda document at: {out_docx}", flush=True)

    return {
        "payload": payload,
        "output_docx_path": out_docx
    }
