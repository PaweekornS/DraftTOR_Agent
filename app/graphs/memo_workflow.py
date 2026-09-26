import re
from typing import Dict, Any
from app.schemas.gov_documents import MemoInputRequest, MemoDraftPayload
from app.services.llm_factory import call_llm
from app.services.fewshot_store import fewshot_store
from app.services.docx_renderer import render_memo_docx

def draft_memo_document(req: MemoInputRequest) -> Dict[str, Any]:
    """
    Drafts an official Thai Government Memorandum (บันทึกข้อความ)
    following the Office of the Prime Minister's Regulations on Office Material B.E. 2526.
    Structure:
    1. ต้นเรื่อง (Background / Origin)
    2. ข้อเท็จจริงและข้อพิจารณา (Facts & Considerations)
    3. ข้อเสนอ (Action / Recommendation) - "จึงเรียนมาเพื่อโปรด..."
    """
    print(f"\n[Memo Pipeline] Drafting official memorandum for: '{req.subject}'...", flush=True)

    # 1. Draft ต้นเรื่อง & ข้อเท็จจริง/ข้อพิจารณา via LLM
    prompt = f"""คุณเป็นเจ้าหน้าที่งานสารบรรณภาครัฐระดับชำนาญการพิเศษ
โปรดร่างเนื้อหา 'บันทึกข้อความ' (หนังสือภายในราชการ) ตามระเบียบสำนักนายกรัฐมนตรีว่าด้วยงานสารบรรณ พ.ศ. ๒๕๒๖

ข้อมูลหนังสือ:
- ส่วนราชการ: {req.agency_name} {req.department_sub}
- เรื่อง: {req.subject}
- เรียน: {req.recipient}
- ข้อมูล/บริบทความต้องการ: {req.raw_context}
- ประเด็นที่ขอให้ดำเนินการ: {req.action_request}

คำสั่ง:
จงร่างเนื้อหาออกเป็น 2 ส่วนหลักด้วยสำนวนภาษาราชการที่ถูกต้อง รัดกุม ชัดเจน:
ส่วนที่ 1: ความเป็นมา/ต้นเรื่อง (ขึ้นต้นด้วย 'ด้วย...' หรือ 'ตามที่...') 1 ย่อหน้า
ส่วนที่ 2: ข้อเท็จจริงและข้อพิจารณา (ขึ้นต้นด้วย 'กลุ่มงาน/ฝ่ายได้พิจารณาแล้วเห็นว่า...' หรือ 'ข้อเท็จจริงปรากฏว่า...') 1-2 ย่อหน้า

รูปแบบผลลัพธ์ (ไม่ต้องใส่เครื่องหมายพิเศษหรือ markdown code block):
=== ต้นเรื่อง ===
[เนื้อความส่วนที่ 1]
=== ข้อพิจารณา ===
[เนื้อความส่วนที่ 2]
"""
    response_text = call_llm([{"role": "user", "content": prompt}])
    
    bg_text = ""
    consid_text = ""
    
    if "=== ต้นเรื่อง ===" in response_text and "=== ข้อพิจารณา ===" in response_text:
        parts = response_text.split("=== ข้อพิจารณา ===")
        bg_part = parts[0].replace("=== ต้นเรื่อง ===", "").strip()
        consid_part = parts[1].strip() if len(parts) > 1 else ""
        bg_text = bg_part
        consid_text = consid_part
    else:
        # Fallback splitting by paragraphs
        paragraphs = [p.strip() for p in response_text.split("\n\n") if p.strip()]
        if len(paragraphs) >= 2:
            bg_text = paragraphs[0]
            consid_text = "\n\n".join(paragraphs[1:])
        else:
            bg_text = f"ด้วย {req.agency_name} มีความประสงค์จะดำเนินการในเรื่อง {req.subject} เพื่อประโยชน์แห่งการบริหารราชการแผ่นดิน"
            consid_text = req.raw_context or fewshot_store.get_memo_consideration_sample()

    # 2. Standardize action request phrasing
    action = req.action_request.strip()
    if not action.startswith("พิจารณา"):
        action = f"พิจารณา{action}"

    payload = MemoDraftPayload(
        agency_name=req.agency_name,
        department_sub=req.department_sub or "",
        doc_number=req.doc_number,
        doc_date=req.doc_date,
        subject=req.subject,
        recipient=req.recipient,
        background_text=bg_text,
        considerations_text=consid_text,
        action_request=action,
        signer_name=req.signer_name,
        signer_position=req.signer_position
    )

    out_docx = render_memo_docx(payload)
    print(f"✓ Generated official Memo document at: {out_docx}", flush=True)

    return {
        "payload": payload,
        "output_docx_path": out_docx
    }
