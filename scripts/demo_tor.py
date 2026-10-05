"""End-to-end demo: draft + verify a realistic TOR with real models, then write what the web
app receives (JSON view) and what the user downloads (.docx).

Usage: python scripts/demo_tor.py [--out data/outputs/demo]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from app.tor import ExportBlocked, draft_and_verify_tor, export_docx, to_view
from app.tor.schemas import ChapterKind as K, ProcurementType, TemplateChapter, TORRequest, TORTemplateSpec

TEMPLATE = TORTemplateSpec(template_id="ebidding_service_over_500k", chapters=[
    TemplateChapter(id="background", title="ความเป็นมาและเหตุผลความจำเป็น", kind=K.TEXT),
    TemplateChapter(id="objectives", title="วัตถุประสงค์", kind=K.LIST),
    TemplateChapter(id="qualifications", title="คุณสมบัติของผู้ยื่นข้อเสนอ", kind=K.LIST,
                    instructions="รวมคุณสมบัติทั่วไปตามกฎหมายและคุณสมบัติเฉพาะด้านผลงาน"),
    TemplateChapter(id="scope", title="ขอบเขตของงาน", kind=K.LIST),
    TemplateChapter(id="spec", title="คุณลักษณะเฉพาะของระบบ", kind=K.LIST,
                    instructions="คุณลักษณะเชิงหน้าที่และประสิทธิภาพ ไม่ระบุยี่ห้อ"),
    TemplateChapter(id="budget", title="วงเงินงบประมาณ", kind=K.BOQ),
    TemplateChapter(id="payment", title="งวดงานและการจ่ายเงิน", kind=K.PAYMENT_SCHEDULE),
    TemplateChapter(id="terms", title="หลักประกันสัญญา ค่าปรับ และการจ้างช่วง", kind=K.TEXT,
                    instructions="กำหนดหลักประกันสัญญา อัตราค่าปรับรายวัน และข้อห้ามจ้างช่วงพร้อมค่าปรับ"),
    TemplateChapter(id="warranty", title="การรับประกันและการบำรุงรักษา", kind=K.LIST),
    TemplateChapter(id="evaluation", title="หลักเกณฑ์การพิจารณาคัดเลือกข้อเสนอ", kind=K.TEXT,
                    instructions="ใช้เกณฑ์ราคาประกอบเกณฑ์อื่น (Price Performance) ระบุน้ำหนักคะแนน"),
])

REQUEST = TORRequest(
    project_name="โครงการพัฒนาระบบสืบค้นเอกสารราชการอัจฉริยะด้วยปัญญาประดิษฐ์",
    agency_name="สำนักงานพัฒนารัฐบาลดิจิทัล (องค์การมหาชน)",
    budget=3_500_000, duration_days=240, procurement_type=ProcurementType.SERVICES, template=TEMPLATE,
    raw_requirements=("ระบบค้นหาเอกสารราชการและมติคณะรัฐมนตรีด้วย AI แบบค้นหาตามความหมาย รองรับภาษาไทย "
                      "ติดตั้งบนคลาวด์ภาครัฐ เชื่อมต่อระบบสารบรรณเดิม มีการทดสอบความมั่นคงปลอดภัย "
                      "อบรมผู้ใช้งาน และรับประกันพร้อมบำรุงรักษา 1 ปี"),
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/outputs/demo")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    t = time.time()
    result = draft_and_verify_tor(REQUEST, actor="demo")
    print(f"drafted + verified in {time.time() - t:.1f}s, revisions={result.report.revisions}, "
          f"passed={result.report.passed}, summary={result.report.summary()}")

    view_path = os.path.join(args.out, "tor_document.json")
    with open(view_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(json.loads(to_view(result).model_dump_json()), ensure_ascii=False, indent=2))
    print("web payload:", view_path)

    docx_path = os.path.join(args.out, "tor.docx")
    try:
        print("download:", export_docx(result, docx_path, actor="demo"))
    except ExportBlocked as e:
        print("final export blocked:", e)
        print("draft download:", export_docx(result, docx_path.replace(".docx", "_draft.docx"), actor="demo", draft=True))


if __name__ == "__main__":
    main()
