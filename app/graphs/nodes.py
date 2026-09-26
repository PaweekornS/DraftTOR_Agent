import json
import re
from typing import Dict, Any, List
from app.graphs.state import TORGraphState
from app.schemas.gov_documents import TORDraftPayload, BudgetItem
from app.services.llm_factory import call_llm
from app.services.fewshot_store import fewshot_store
from app.services.docx_renderer import render_tor_docx

ALL_SECTIONS = [
    "background_and_rationale",
    "objectives",
    "budget_breakdown",
    "vendor_qualifications",
    "scope_of_work",
    "deliverables_and_payments",
    "evaluation_criteria"
]

def clean_bullet_list(text: str) -> List[str]:
    """Clean plain text / markdown / bullet lines into a python string list."""
    lines = []
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    content = match.group(1).strip() if match else text.strip()

    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass

    for line in content.split('\n'):
        cleaned = re.sub(r'^\s*[\d\.\-\*\•\)]+\s*', '', line).strip()
        cleaned = cleaned.strip('"\'[],')
        if cleaned and len(cleaned) > 3 and not cleaned.startswith('{') and not cleaned.startswith('}'):
            lines.append(cleaned)
    return lines

def extract_and_plan_node(state: TORGraphState) -> Dict[str, Any]:
    print("\n[Node 1: extract_and_plan] Initializing drafting pipeline...", flush=True)
    return {
        "sections_to_draft": ALL_SECTIONS,
        "current_section_index": 0,
        "drafted_sections": {},
        "errors": []
    }

def draft_section_worker_node(state: TORGraphState) -> Dict[str, Any]:
    idx = state["current_section_index"]
    section_name = state["sections_to_draft"][idx]
    print(f"\n[Node 2: draft_section_worker] Drafting Section {idx+1}/{len(ALL_SECTIONS)}: '{section_name}'...", flush=True)
    
    project_name = state["project_name"]
    agency_name = state["agency_name"]
    budget = state["budget"]
    duration_days = state["duration_days"]
    raw_req = state["raw_requirements"]
    drafted = dict(state.get("drafted_sections", {}))

    if section_name == "background_and_rationale":
        bg_example = fewshot_store.get_background_example()
        prompt = f"""คุณเป็นเจ้าหน้าที่พัสดุอาวุโสและผู้เชี่ยวชาญการร่าง TOR เอกสารราชการไทย
โปรดร่างหัวข้อ '1. ความเป็นมาและเหตุผลความจำเป็น' สำหรับโครงการต่อไปนี้:
- ชื่อโครงการ: {project_name}
- หน่วยงาน: {agency_name}
- งบประมาณ: {budget:,.2f} บาท
- ความต้องการเบื้องต้น: {raw_req}

ตัวอย่างสำนวนราชการที่ดี (จาก DGA):
\"\"\"{bg_example}\"\"\"

คำสั่ง:
เขียนความเป็นมาและเหตุผลความจำเป็นอย่างเป็นทางการ อ้างอิงยุทธศาสตร์ชาติ หรือการเพิ่มประสิทธิภาพภาครัฐ ความยาว 1-2 ย่อหน้า
ไม่ต้องใส่หัวข้อเลข ให้เขียนเนื้อความโดยตรง"""
        res = call_llm([{"role": "user", "content": prompt}])
        drafted[section_name] = res.strip() if res else fewshot_store.get_background_example()

    elif section_name == "objectives":
        prompt = f"""คุณเป็นผู้เชี่ยวชาญการร่าง TOR ภาครัฐ
โปรดกำหนด 'วัตถุประสงค์' ของโครงการ: '{project_name}'
หน่วยงาน: {agency_name}
ความต้องการ: {raw_req}

คำสั่ง:
เขียนข้อความวัตถุประสงค์ 3-4 ข้อ ที่ขึ้นต้นด้วย 'เพื่อ...' เช่น:
- เพื่อพัฒนาระบบ...
- เพื่อยกระดับการให้บริการ...
- เพื่อเสริมสร้างประสิทธิภาพ...
เขียนเป็นรายการข้อๆ บรรทัดละข้อ"""
        res = call_llm([{"role": "user", "content": prompt}])
        obj_list = clean_bullet_list(res)
        drafted[section_name] = obj_list if len(obj_list) >= 2 else fewshot_store.get_objectives_example()

    elif section_name == "budget_breakdown":
        # Deterministic Budget Calculator in Python
        # Generate 3-4 realistic component names based on project
        prompt = f"""สำหรับโครงการ '{project_name}' วงเงินงบประมาณ {budget:,.2f} บาท
โปรดระบุ 3-4 หมวดหมู่ค่าใช้จ่ายหลัก (เช่น ค่าพัฒนาระบบซอฟต์แวร์/AI, ค่าติดตั้งระบบคลาวด์/ฮาร์ดแวร์, ค่าทดสอบความปลอดภัย, ค่าฝึกอบรมและถ่ายทอดเทคโนโลยี)
เขียนเฉพาะชื่อรายการ บรรทัดละ 1 รายการ"""
        res = call_llm([{"role": "user", "content": prompt}])
        item_names = clean_bullet_list(res)
        if len(item_names) < 3:
            item_names = [
                "งานออกแบบและพัฒนาระบบซอฟต์แวร์หลัก",
                "งานจัดเตรียมระบบโครงสร้างพื้นฐานและเชื่อมโยงข้อมูล",
                "งานทดสอบความมั่นคงปลอดภัยและประสิทธิภาพระบบ (UAT/Security Audit)",
                "งานฝึกอบรม ถ่ายทอดเทคโนโลยี และจัดทำคู่มือการใช้งาน"
            ]

        # Weights: 50%, 25%, 15%, 10%
        weights = [0.50, 0.25, 0.15, 0.10]
        if len(item_names) == 3:
            weights = [0.55, 0.30, 0.15]
        elif len(item_names) > 4:
            item_names = item_names[:4]

        budget_items = []
        allocated = 0.0
        for i, name in enumerate(item_names):
            if i == len(item_names) - 1:
                item_total = budget - allocated # Ensure exact 100% sum
            else:
                item_total = round(budget * weights[i], 2)
                allocated += item_total
            
            budget_items.append(BudgetItem(
                name=name,
                qty=1,
                unit="ระบบ" if "ระบบ" in name else "รายการ",
                unit_price=item_total,
                total_price=item_total
            ))
        drafted[section_name] = [b.model_dump() for b in budget_items]

    elif section_name == "vendor_qualifications":
        std_quals = fewshot_store.get_standard_vendor_qualifications()
        prompt = f"""สำหรับโครงการ: '{project_name}' งบประมาณ {budget:,.2f} บาท
โปรดกำหนดคุณสมบัติเฉพาะด้านเทคนิคหรือผลงานของผู้ยื่นข้อเสนอ 2 ข้อ เช่น:
- มีผลงานด้านที่เกี่ยวข้องในวงเงินสัญญาไม่น้อยกว่า...
- มีบุคลากรหรือผู้เชี่ยวชาญที่มีทักษะ...
เขียนเป็น 2 ข้อ บรรทัดละข้อ"""
        res = call_llm([{"role": "user", "content": prompt}])
        tech_quals = clean_bullet_list(res)
        if not tech_quals:
            tech_quals = [
                f"มีผลงานด้านการพัฒนาระบบเทคโนโลยีสารสนเทศหรือปัญญาประดิษฐ์ในวงเงินสัญญาไม่น้อยกว่า {budget * 0.3:,.2f} บาท ในสัญญาเดียว",
                "มีบุคลากรหลักที่มีประสบการณ์ด้านการออกแบบและพัฒนาระบบไม่น้อยกว่า 3 ปี"
            ]
        drafted[section_name] = std_quals + tech_quals

    elif section_name == "scope_of_work":
        prompt = f"""คุณเป็นหัวหน้าคณะกรรมการกำหนดร่างขอบเขตของงาน (TOR)
โปรดร่าง 'ขอบเขตของงานและข้อกำหนดเฉพาะ (Scope of Work)' สำหรับโครงการ:
- โครงการ: {project_name}
- รายละเอียดความต้องการ: {raw_req}
- ระยะเวลา: {duration_days} วัน

คำสั่ง:
แตกรายละเอียดขอบเขตงานออกมาเป็น 4-5 ข้อย่อยสำคัญ (เช่น การวิเคราะห์ออกแบบ, การพัฒนาติดตั้งระบบ, การทดสอบระบบ UAT, การฝึกอบรม, การรับประกันและบำรุงรักษา)
เขียนเป็นรายการข้อๆ บรรทัดละข้อ"""
        res = call_llm([{"role": "user", "content": prompt}])
        sow = clean_bullet_list(res)
        drafted[section_name] = sow if len(sow) >= 3 else [
            "ศึกษา วิเคราะห์ และออกแบบสถาปัตยกรรมระบบตามมาตรฐาน",
            "ดำเนินการพัฒนาระบบ AI และเชื่อมโยงข้อมูลตามข้อกำหนด",
            "ทำการทดสอบระบบด้านความถูกต้องและความมั่นคงปลอดภัย (UAT)",
            "จัดฝึกอบรมการใช้งานและถ่ายทอดองค์ความรู้ให้แก่บุคลากร",
            "ให้บริการดูแล บำรุงรักษา และแก้ไขปัญหาของระบบเป็นเวลา 1 ปี"
        ]

    elif section_name == "deliverables_and_payments":
        prompt = f"""โปรดร่าง 'งวดงานและการเบิกจ่ายเงิน' สำหรับโครงการ: '{project_name}'
ระยะเวลาดำเนินงานทั้งหมด: {duration_days} วัน
งบประมาณ: {budget:,.2f} บาท

คำสั่ง:
แบ่งงวดงานออกเป็น 3-4 งวด โดยแต่ละงวดให้ระบุ ร้อยละของการจ่ายเงิน, สิ่งที่ต้องส่งมอบ, และกรอบเวลา (วัน) ผลรวมร้อยละต้องเท่ากับ 100%
เขียนเป็นข้อๆ บรรทัดละข้อ เช่น:
- งวดที่ 1 (ร้อยละ 20): ส่งมอบแผนการดำเนินงานและสถาปัตยกรรมระบบ ภายใน 30 วัน
- งวดที่ 2 (ร้อยละ 40): ส่งมอบระบบรุ่นต้นแบบและผลการทดสอบเบื้องต้น ภายใน 90 วัน
- งวดที่ 3 (ร้อยละ 40): ส่งมอบระบบฉบับสมบูรณ์ คู่มือ และผลการฝึกอบรม ภายใน {duration_days} วัน"""
        res = call_llm([{"role": "user", "content": prompt}])
        deliv = clean_bullet_list(res)
        drafted[section_name] = deliv if len(deliv) >= 2 else [
            "งวดที่ 1 (ร้อยละ 20): ส่งมอบแผนการดำเนินงาน เอกสารการวิเคราะห์และออกแบบระบบ ภายใน 30 วัน",
            f"งวดที่ 2 (ร้อยละ 40): พัฒนาและติดตั้งระบบรุ่นทดสอบ พร้อมรายงานผลการทดสอบ ภายใน {int(duration_days * 0.6)} วัน",
            f"งวดที่ 3 (ร้อยละ 40): ส่งมอบระบบฉบับสมบูรณ์ รายงานผลการฝึกอบรม และคู่มือการใช้งาน ภายใน {duration_days} วัน"
        ]

    elif section_name == "evaluation_criteria":
        drafted[section_name] = fewshot_store.get_standard_evaluation_criteria()

    return {
        "drafted_sections": drafted,
        "current_section_index": idx + 1
    }

def bureaucratic_polisher_node(state: TORGraphState) -> Dict[str, Any]:
    print("\n[Node 3: bureaucratic_polisher] Reviewing and validating official schema...", flush=True)
    drafted = state["drafted_sections"]
    
    # Parse budget breakdown into BudgetItem models
    raw_breakdown = drafted.get("budget_breakdown", [])
    breakdown_models = [BudgetItem(**b) if isinstance(b, dict) else b for b in raw_breakdown]

    payload = TORDraftPayload(
        project_name=state["project_name"],
        agency_name=state["agency_name"],
        budget=state["budget"],
        duration_days=state["duration_days"],
        background_and_rationale=drafted.get("background_and_rationale", ""),
        objectives=drafted.get("objectives", []),
        budget_breakdown=breakdown_models,
        vendor_qualifications=drafted.get("vendor_qualifications", []),
        scope_of_work=drafted.get("scope_of_work", []),
        deliverables_and_payments=drafted.get("deliverables_and_payments", []),
        evaluation_criteria=drafted.get("evaluation_criteria", "")
    )
    
    return {
        "drafted_sections": payload.model_dump()
    }

def render_docx_node(state: TORGraphState) -> Dict[str, Any]:
    print("\n[Node 4: render_docx_node] Rendering Word (.docx) document with docxtpl...", flush=True)
    payload_dict = state["drafted_sections"]
    payload = TORDraftPayload(**payload_dict)
    
    out_path = render_tor_docx(payload, template_filename="tor_template.docx")
    print(f"✓ Generated official TOR document at: {out_path}", flush=True)
    
    return {
        "output_docx_path": out_path
    }
