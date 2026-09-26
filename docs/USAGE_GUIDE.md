# 📖 Usage Guide: Drafting Thai Government Documents

This guide explains how to programmatically generate official Thai Government documents using the unified `DocumentOrchestrator`.

---

## 1. Environment Setup

Ensure your `.env` is configured (see `env.example`):

```bash
OPENROUTER_API_KEY="your-openrouter-api-key"
LLM_MODEL_NAME="qwen/qwen3.5-9b"
LLM_BASE_URL="https://openrouter.ai/api/v1"
OUTPUT_DIR="data/outputs"
TEMPLATE_DIR="app/templates"
```

Install requirements:
```bash
pip install -r requirements.txt # or install docxtpl python-docx langgraph langchain-core openai pydantic
```

---

## 2. Drafting a Terms of Reference (TOR)

```python
from app.schemas.gov_documents import DocumentType, TORInputRequest
from app.graphs.document_orchestrator import document_orchestrator

# 1. Define Request
request = TORInputRequest(
    project_name="โครงการพัฒนาระบบสืบค้นข้อมูลอัจฉริยะ (AI Smart Search)",
    agency_name="สำนักงานพัฒนารัฐบาลดิจิทัล (องค์การมหาชน)",
    budget=3500000.00,
    raw_requirements="ระบบสืบค้น AI Semantic Search สืบค้นเอกสารมติคณะรัฐมนตรี พร้อม UAT และอบรม 365 วัน",
    duration_days=365
)

# 2. Generate
result = document_orchestrator.draft_document(DocumentType.TOR, request)

print(f"Generated TOR document at: {result['output_docx_path']}")
```

---

## 3. Drafting an Official Memorandum (บันทึกข้อความ)

```python
from app.schemas.gov_documents import DocumentType, MemoInputRequest
from app.graphs.document_orchestrator import document_orchestrator

request = MemoInputRequest(
    agency_name="กรมพัฒนาธุรกิจการค้า",
    department_sub="กองเทคโนโลยีสารสนเทศ",
    doc_number="พณ ๐๘๐๕/ว ๑๒๓๔",
    doc_date="๒๖ กันยายน ๒๕๖๙",
    subject="ขออนุมัติแต่งตั้งคณะกรรมการจัดทำร่างขอบเขตของงาน (TOR)",
    recipient="อธิบดีกรมพัฒนาธุรกิจการค้า",
    raw_context="เนื่องจากระบบฐานข้อมูลเดิมมีอายุเกิน 5 ปี จำเป็นต้องจัดหาระบบคลาวด์และ AI ยกระดับบริการ",
    action_request="พิจารณาอนุมัติให้แต่งตั้งคณะกรรมการตามรายชื่อที่เสนอ",
    signer_name="นายสมชาย บริหารงานดี",
    signer_position="ผู้อำนวยการกองเทคโนโลยีสารสนเทศ"
)

result = document_orchestrator.draft_document(DocumentType.MEMO, request)
print(f"Generated Memo document at: {result['output_docx_path']}")
```

---

## 4. Drafting a Meeting Agenda (ระเบียบวาระการประชุม)

```python
from app.schemas.gov_documents import DocumentType, MeetingAgendaRequest
from app.graphs.document_orchestrator import document_orchestrator

request = MeetingAgendaRequest(
    committee_name="คณะกรรมการขับเคลื่อนรัฐบาลดิจิทัลและความมั่นคงปลอดภัยไซเบอร์",
    meeting_no=2,
    meeting_year=2569,
    meeting_date="วันอังคารที่ ๑๕ ตุลาคม ๒๕๖๙",
    meeting_time="๐๙.๓๐ - ๑๒.๐๐ น.",
    meeting_location="ห้องประชุมจินดาภรณ์ อาคารกระทรวงดิจิทัลฯ",
    raw_agenda_topics="""
    - รายงานผลการทดสอบระบบ CSOC ประจำเดือนกันยายน
    - พิจารณาร่างข้อกำหนด TOR จัดซื้อระบบเฝ้าระวังภัยคุกคามทางไซเบอร์
    - พิจารณาแนวทางการจัดการงบประมาณเหลือจ่ายประจำปี
    """
)

result = document_orchestrator.draft_document(DocumentType.MEETING_AGENDA, request)
print(f"Generated Meeting Agenda at: {result['output_docx_path']}")
```

---

## 5. Running Automated Evaluations

To verify all test gates and inspect the scorecard:

```bash
python tests/test_evaluation_suite.py
```
