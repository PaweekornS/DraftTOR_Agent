import os
import sys
import time
import docx
from app.graphs.workflow import tor_graph
from app.schemas.tor_document import TORInputRequest

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=" * 80)
    print("      PROOFOF CONCEPT: THAI GOVERNMENT TOR DRAFTING AGENT (PoC)       ")
    print("=" * 80)

    # 1. Realistic GovTech Project Input
    input_req = TORInputRequest(
        project_name="โครงการจัดจ้างพัฒนาระบบ AI Chatbot อัจฉริยะสำหรับตอบคำถามระเบียบและเอกสารราชการ",
        agency_name="สำนักงานพัฒนารัฐบาลดิจิทัล (องค์การมหาชน)",
        budget=1500000.0,
        duration_days=180,
        raw_requirements=(
            "ต้องการระบบแชทบอท AI ที่ใช้เทคโนโลยี Retrieval-Augmented Generation (RAG) "
            "เชื่อมโยงกับฐานข้อมูลระเบียบสำนักนายกรัฐมนตรี และ พ.ร.บ. การจัดซื้อจัดจ้างฯ "
            "สามารถตอบคำถามข้อกฎหมายและระเบียบราชการได้อย่างแม่นยำ พร้อมระบุแหล่งอ้างอิง (Citations) "
            "มีหน้าจอ Web Portal สำหรับเจ้าหน้าที่และผู้ดูแลระบบ (Admin) "
            "มีการทดสอบความปลอดภัยตามมาตรฐาน และมีการฝึกอบรมถ่ายทอดเทคโนโลยีให้เจ้าหน้าที่"
        )
    )

    print(f"\n[Project Name]   : {input_req.project_name}")
    print(f"[Agency]         : {input_req.agency_name}")
    print(f"[Budget]         : {input_req.budget:,.2f} บาท")
    print(f"[Duration]       : {input_req.duration_days} วัน")
    print(f"[Raw Spec]       : {input_req.raw_requirements[:120]}...\n")

    # 2. Prepare LangGraph Initial State
    initial_state = {
        "project_name": input_req.project_name,
        "agency_name": input_req.agency_name,
        "budget": input_req.budget,
        "duration_days": input_req.duration_days,
        "raw_requirements": input_req.raw_requirements,
        "sections_to_draft": [],
        "current_section_index": 0,
        "drafted_sections": {},
        "output_docx_path": None,
        "errors": []
    }

    # 3. Execute LangGraph Pipeline
    start_time = time.time()
    print(">>> Executing LangGraph state machine...")
    final_state = tor_graph.invoke(initial_state)
    elapsed = time.time() - start_time

    # 4. Verify & Validate Output
    output_path = final_state.get("output_docx_path")
    print("\n" + "=" * 80)
    print("                          EXECUTION REPORT                           ")
    print("=" * 80)
    print(f"Total Execution Time : {elapsed:.2f} seconds")
    print(f"Generated Docx Path  : {output_path}")

    if not output_path or not os.path.exists(output_path):
        print("❌ Error: Output .docx file was not generated!")
        sys.exit(1)

    file_size = os.path.getsize(output_path)
    print(f"File Size            : {file_size:,} bytes")

    # Read back generated Word document
    doc = docx.Document(output_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    print(f"Document Paragraphs  : {len(paragraphs)} paragraphs")

    print("\n--- SAMPLE EXTRACTED CONTENT FROM GENERATED WORD DOCUMENT ---")
    for p in paragraphs[:15]:
        print(f"  • {p}")

    print("\n" + "=" * 80)
    print("✓ PoC SUCCESS: Legally structured Thai TOR document drafted and rendered!")
    print("=" * 80)

if __name__ == "__main__":
    main()
