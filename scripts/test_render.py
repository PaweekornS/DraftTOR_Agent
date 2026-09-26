from docxtpl import DocxTemplate
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Load Ground Truth extracted from DGA
with open('data/ground_truth/parsed_json/DGA_AI_Smart_Search_TOR.json', encoding='utf-8') as f:
    gt_data = json.load(f)

payload = {
    "project_name": "งานจ้างบริการระบบค้นหาด้วยเทคโนโลยีปัญญาประดิษฐ์ (Government AI Smart Search)",
    "agency_name": "สำนักงานพัฒนารัฐบาลดิจิทัล (องค์การมหาชน)",
    "budget": 15000000.0,
    "duration_days": 365,
    "background_and_rationale": gt_data.get("background_and_rationale", "ความเป็นมาของโครงการ..."),
    "objectives": [
        "เพื่อพัฒนาและให้บริการระบบค้นหาด้วยเทคโนโลยีปัญญาประดิษฐ์ (Government AI Smart Search) ที่มีความถูกต้อง แม่นยำ",
        "เพื่อยกระดับการให้บริการประชาชนผ่านแอปพลิเคชันทางรัฐ",
        "เพื่อสนับสนุนการปฏิบัติงานของเจ้าหน้าที่รัฐในการสืบค้นข้อมูลระเบียบและเอกสารราชการ"
    ],
    "vendor_qualifications": [
        "มีคุณสมบัติตาม พ.ร.บ. การจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560",
        "ไม่เป็นผู้มีผลประโยชน์ร่วมกันกับผู้ยื่นข้อเสนอรายอื่นที่เข้ายื่นข้อเสนอให้แก่สำนักงาน",
        "ไม่เป็นผู้ถูกระบุชื่อไว้ในบัญชีรายชื่อผู้ทิ้งงานของทางราชการ",
        "มีผลงานด้านการพัฒนาระบบ AI หรือ Natural Language Processing มูลค่าสัญญาไม่น้อยกว่า 3,000,000 บาท"
    ],
    "scope_of_work": [
        "วิเคราะห์ ออกแบบ และติดตั้งระบบ Government AI Smart Search",
        "เชื่อมโยงข้อมูลและสร้าง Data Pipeline จากระบบสารสนเทศภาครัฐ",
        "จัดทำระบบความปลอดภัยตามมาตรฐาน ISO 27001",
        "จัดฝึกอบรมบุคลากรและถ่ายทอดองค์ความรู้จำนวนไม่น้อยกว่า 50 คน"
    ],
    "deliverables_and_payments": [
        "งวดที่ 1 (20%): ส่งมอบรายงานแผนการดำเนินงานและสถาปัตยกรรมระบบ ภายใน 30 วัน",
        "งวดที่ 2 (30%): ติดตั้งระบบค้นหา AI ต้นแบบและเชื่อมต่อ API ภายใน 120 วัน",
        "งวดที่ 3 (30%): ทำการทดสอบระบบ (UAT) และผลการประเมินความปลอดภัย ภายใน 240 วัน",
        "งวดที่ 4 (20%): อบรมบุคลากรและส่งมอบคู่มือพร้อมซอร์สโค้ดฉบับสมบูรณ์ ภายใน 365 วัน"
    ],
    "evaluation_criteria": "พิจารณาตัดสินโดยใช้เกณฑ์ราคาประกอบเกณฑ์คุณภาพ (Price Performance) โดยมีสัดส่วนคะแนนด้านเทคนิค 70% และด้านราคา 30%"
}

os.makedirs('data/outputs', exist_ok=True)
doc = DocxTemplate('app/templates/tor_template.docx')
doc.render(payload)
output_path = 'data/outputs/test_rendered_dga_tor.docx'
doc.save(output_path)
print(f"Successfully rendered test docx to: {output_path} (size: {os.path.getsize(output_path)} bytes)")
