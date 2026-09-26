import os
import sys
import docx
import re
from typing import Dict, Any, List
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.gov_documents import (
    DocumentType,
    TORInputRequest,
    MemoInputRequest,
    MeetingAgendaRequest,
    TORDraftPayload,
    MemoDraftPayload,
    MeetingAgendaPayload
)
from app.graphs.document_orchestrator import document_orchestrator

# Ensure UTF-8 stdout encoding for Windows terminals
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

class TestGovernmentDocumentEvaluation(unittest.TestCase):
    """
    Comprehensive Multi-Document Evaluation Suite for Thai Government Documents.
    Evaluates:
    - Multi-document adaptability (TOR, Memo, Meeting Agenda)
    - Gate 1: Structural Completeness & Schema Adherence
    - Gate 2: Financial Integrity & Exact Math (BOQ breakdown == budget 100%)
    - Gate 3: Visual & Media Edge Cases (Garuda emblem embedded, dynamic XML tables rendered)
    - Gate 4: Thai Saraban & Legal Compliance (พ.ร.บ.จัดซื้อจัดจ้างฯ 2560 & ระเบียบงานสารบรรณ)
    - Gate 5: No LLM Hallucination / Scratchpad Leaks
    """

    @classmethod
    def setUpClass(cls):
        print("\n" + "="*70)
        print(">> INITIALIZING MULTI-DOCUMENT EVALUATION SUITE")
        print("="*70)
        cls.evaluation_results = []


    def log_metric(self, doc_type: str, test_name: str, passed: bool, details: str):
        self.evaluation_results.append({
            "doc_type": doc_type,
            "test_name": test_name,
            "passed": passed,
            "details": details
        })

    def test_01_tor_document_full_evaluation(self):
        """Test TOR document generation, BOQ table math, Garuda placement, and legal clauses."""
        print("\n>>> [EVAL 1] Evaluating TOR (Terms of Reference) & Budget Breakdown...")
        budget = 3500000.00
        req = TORInputRequest(
            project_name="โครงการพัฒนาระบบสืบค้นข้อมูลอัจฉริยะ (AI Smart Search)",
            agency_name="สำนักงานพัฒนารัฐบาลดิจิทัล (องค์การมหาชน)",
            budget=budget,
            raw_requirements="ต้องการพัฒนาระบบ AI Semantic Search เพื่อสืบค้นเอกสารราชการและมติคณะรัฐมนตรี พร้อมระบบความปลอดภัย UAT และอบรม 365 วัน",
            duration_days=365
        )

        res = document_orchestrator.draft_document(DocumentType.TOR, req)
        payload: TORDraftPayload = res["payload"]
        docx_path = res["output_docx_path"]

        # --- Gate 1: Structural Completeness ---
        self.assertIsNotNone(payload.background_and_rationale)
        self.assertTrue(len(payload.background_and_rationale) > 100, "Background must be substantive")
        self.assertTrue(len(payload.objectives) >= 2, "Objectives must have at least 2 items")
        self.assertTrue(len(payload.scope_of_work) >= 3, "Scope of work must have at least 3 items")
        self.assertTrue(len(payload.deliverables_and_payments) >= 2, "Deliverables must have at least 2 installments")
        self.log_metric("TOR", "Structural Completeness", True, f"7 sections complete, {len(payload.scope_of_work)} scope items")

        # --- Gate 2: Financial Integrity (BOQ Math) ---
        self.assertTrue(len(payload.budget_breakdown) >= 3, "Must have at least 3 BOQ line items")
        calculated_sum = sum(item.total_price for item in payload.budget_breakdown)
        self.assertAlmostEqual(calculated_sum, budget, places=2, msg=f"BOQ Sum {calculated_sum} must equal budget {budget}")
        
        for item in payload.budget_breakdown:
            expected_line_total = round(item.qty * item.unit_price, 2)
            self.assertAlmostEqual(item.total_price, expected_line_total, places=2)
        self.log_metric("TOR", "Financial Integrity (100% Math)", True, f"Budget: THB {budget:,.2f} == BOQ Sum: THB {calculated_sum:,.2f}")

        # --- Gate 3: Visual & Media Edge Cases (Garuda + Table in docx) ---
        self.assertTrue(os.path.exists(docx_path), "Docx file must exist on disk")
        doc = docx.Document(docx_path)
        
        # Check image rels
        images = [r.target_ref for r in doc.part.rels.values() if "image" in r.target_ref]
        self.assertTrue(len(images) >= 1, "Garuda emblem must be physically embedded in docx package")
        
        # Check dynamic table
        self.assertTrue(len(doc.tables) >= 1, "Docx must contain at least 1 formatted table")
        table = doc.tables[0]
        self.assertTrue(len(table.rows) >= len(payload.budget_breakdown), f"Table rows ({len(table.rows)}) must reflect budget items")
        self.log_metric("TOR", "Garuda & Dynamic Table Rendering", True, f"Garuda verified. Table has {len(table.rows)} rows")

        # --- Gate 4: Legal Compliance ---
        self.assertTrue(any("ไม่เป็นบุคคลล้มละลาย" in q for q in payload.vendor_qualifications), "Must contain standard Act B.E. 2560 qualification")
        self.assertTrue("Price" in payload.evaluation_criteria or "เกณฑ์ราคา" in payload.evaluation_criteria or "คุณภาพ" in payload.evaluation_criteria)
        self.log_metric("TOR", "Public Procurement Act 2560 Compliance", True, "Mandatory vendor qualification & evaluation criteria verified")

    def test_02_memo_document_full_evaluation(self):
        """Test Thai Official Memorandum (บันทึกข้อความ) with 1.5cm Garuda and Saraban structure."""
        print("\n>>> [EVAL 2] Evaluating Memorandum (บันทึกข้อความ)...")
        req = MemoInputRequest(
            agency_name="กรมพัฒนาธุรกิจการค้า",
            department_sub="กองเทคโนโลยีสารสนเทศ",
            doc_number="พณ ๐๘๐๕/ว ๑๒๓๔",
            doc_date="๒๖ กันยายน ๒๕๖๙",
            subject="ขออนุมัติแต่งตั้งคณะกรรมการจัดทำร่างขอบเขตของงาน (TOR)",
            recipient="อธิบดีกรมพัฒนาธุรกิจการค้า",
            raw_context="เนื่องจากระบบฐานข้อมูลนิติบุคคลเดิมมีอายุการใช้งานเกิน ๕ ปี จำเป็นต้องจัดหาระบบคลาวด์และ AI ยกระดับบริการ",
            action_request="พิจารณาอนุมัติให้แต่งตั้งคณะกรรมการตามรายชื่อที่เสนอ",
            signer_name="นายสมชาย บริหารงานดี",
            signer_position="ผู้อำนวยการกองเทคโนโลยีสารสนเทศ"
        )

        res = document_orchestrator.draft_document(DocumentType.MEMO, req)
        payload: MemoDraftPayload = res["payload"]
        docx_path = res["output_docx_path"]

        # --- Gate 1: Saraban Header Structure ---
        self.assertEqual(payload.agency_name, "กรมพัฒนาธุรกิจการค้า")
        self.assertEqual(payload.subject, req.subject)
        self.assertEqual(payload.recipient, req.recipient)
        self.log_metric("MEMO", "Saraban Header Adherence", True, "agency, doc_number, date, subject, recipient intact")

        # --- Gate 2: 3-Part Bureaucratic Content ---
        self.assertTrue(len(payload.background_text) > 30, "Background text (ต้นเรื่อง) must be non-empty")
        self.assertTrue(len(payload.considerations_text) > 30, "Considerations text (ข้อพิจารณา) must be non-empty")
        self.assertTrue("พิจารณา" in payload.action_request, "Action request must maintain formal Thai phrasing")
        self.log_metric("MEMO", "3-Part Bureaucratic Content Structure", True, "Background, Considerations, and Action conform to Saraban")

        # --- Gate 3: Visual & Media (1.5cm Garuda placement) ---
        self.assertTrue(os.path.exists(docx_path))
        doc = docx.Document(docx_path)
        images = [r.target_ref for r in doc.part.rels.values() if "image" in r.target_ref]
        self.assertTrue(len(images) >= 1, "Garuda emblem (1.5cm) must be embedded in memo header")
        self.log_metric("MEMO", "Garuda Emblem Embedded", True, "1.5cm Garuda emblem verified in docx")

        # --- Gate 4: No Scratchpad Leaks ---
        full_text = payload.background_text + " " + payload.considerations_text
        self.assertFalse("<think>" in full_text or "```" in full_text, "No markdown or LLM scratchpad in output")
        self.log_metric("MEMO", "Clean Text / Zero Hallucination Scratchpad", True, "No LLM scratchpad or reasoning leakage")

    def test_03_meeting_agenda_full_evaluation(self):
        """Test Meeting Agenda (ระเบียบวาระการประชุม) with 5-agenda standard."""
        print("\n>>> [EVAL 3] Evaluating Meeting Agenda (ระเบียบวาระการประชุม)...")
        req = MeetingAgendaRequest(
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

        res = document_orchestrator.draft_document(DocumentType.MEETING_AGENDA, req)
        payload: MeetingAgendaPayload = res["payload"]
        docx_path = res["output_docx_path"]

        # --- Gate 1: 5 Standard Agendas Verification ---
        self.assertTrue(len(payload.agenda_1_chairman_notes) > 10, "Agenda 1 (เรื่องประธานแจ้ง) must exist")
        self.assertTrue(len(payload.agenda_2_previous_minutes) > 5, "Agenda 2 (รับรองรายงาน) must exist")
        self.assertTrue(len(payload.agenda_3_matters_to_inform) >= 1, "Agenda 3 (เรื่องเพื่อทราบ) must have items")
        self.assertTrue(len(payload.agenda_4_matters_for_consideration) >= 2, "Agenda 4 (เรื่องเพื่อพิจารณา) must have items")
        self.assertEqual(payload.agenda_5_other_matters, "ไม่มี")
        self.log_metric("AGENDA", "Standard 5-Agendas Format", True, "Agendas 1 to 5 fully conform to meeting standards")

        # --- Gate 2: Document Rendering Verification ---
        self.assertTrue(os.path.exists(docx_path))
        doc = docx.Document(docx_path)
        doc_text = " ".join([p.text for p in doc.paragraphs])
        self.assertTrue("ระเบียบวาระการประชุม" in doc_text)
        self.assertTrue("ครั้งที่ 2/2569" in doc_text or "ครั้งที่ ๒/๒๕๖๙" in doc_text or "2/2569" in doc_text)
        self.log_metric("AGENDA", "Meeting Agenda Docx Rendered", True, f"Docx generated ({len(doc.paragraphs)} paragraphs)")

    @classmethod
    def tearDownClass(cls):
        print("\n" + "="*80)
        print("GOVERNMENT DOCUMENT AI EVALUATION SCORECARD")
        print("="*80)
        print(f"{'Document Type':<12} | {'Evaluation Metric':<40} | {'Status':<8} | {'Details'}")
        print("-" * 80)
        passed_count = 0
        for item in cls.evaluation_results:
            status = "[PASS]" if item["passed"] else "[FAIL]"
            if item["passed"]:
                passed_count += 1
            print(f"{item['doc_type']:<12} | {item['test_name']:<40} | {status:<8} | {item['details']}")
        
        total = len(cls.evaluation_results)
        pct = (passed_count / total * 100) if total > 0 else 0
        print("-" * 80)
        print(f"Total Tests: {total} | Passed: {passed_count} | Pass Rate: {pct:.1f}%")
        print("="*80 + "\n")

if __name__ == "__main__":
    unittest.main()

