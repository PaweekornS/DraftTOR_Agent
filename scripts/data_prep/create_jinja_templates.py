import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def set_thai_font(run, font_name="TH Sarabun PSK", size_pt=16, bold=False):
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.bold = bold

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set cell padding in dxa."""
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def create_tor_template(output_path, garuda_path="app/assets/garuda.png"):
    doc = docx.Document()
    
    # Page setup: Top 2.5cm, Bottom 2.0cm, Left 3.0cm, Right 2.0cm
    for s in doc.sections:
        s.top_margin = Inches(0.98)     # ~2.5 cm
        s.bottom_margin = Inches(0.79)  # ~2.0 cm
        s.left_margin = Inches(1.18)    # ~3.0 cm
        s.right_margin = Inches(0.79)   # ~2.0 cm

    # Document Header with Garuda Emblem
    p_logo = doc.add_paragraph()
    p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if os.path.exists(garuda_path):
        # 3.0 cm for official cover
        p_logo.add_run().add_picture(garuda_path, width=Inches(1.18))  # ~3.0 cm

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p_title.add_run("ร่างขอบเขตของงาน (Terms of Reference : TOR)\n")
    set_thai_font(r1, size_pt=18, bold=True)
    r2 = p_title.add_run("โครงการ: {{ project_name }}\n")
    set_thai_font(r2, size_pt=16, bold=True)
    r3 = p_title.add_run("หน่วยงาน: {{ agency_name }} | งบประมาณรวมทั้งสิ้น: {{ '{:,.2f}'.format(budget) }} บาท\n")
    set_thai_font(r3, size_pt=16, bold=False)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 1. Background
    p_bg_h = doc.add_paragraph()
    r = p_bg_h.add_run("1. ความเป็นมาและเหตุผลความจำเป็น")
    set_thai_font(r, size_pt=16, bold=True)
    p_bg = doc.add_paragraph()
    p_bg.paragraph_format.first_line_indent = Inches(0.5)
    r = p_bg.add_run("{{ background_and_rationale }}")
    set_thai_font(r, size_pt=16)

    # 2. Objectives
    p_obj_h = doc.add_paragraph()
    r = p_obj_h.add_run("2. วัตถุประสงค์")
    set_thai_font(r, size_pt=16, bold=True)
    p_obj = doc.add_paragraph()
    p_obj.paragraph_format.first_line_indent = Inches(0.5)
    r = p_obj.add_run("{% for obj in objectives %}")
    set_thai_font(r, size_pt=16)
    p_obj_item = doc.add_paragraph()
    p_obj_item.paragraph_format.first_line_indent = Inches(0.5)
    r = p_obj_item.add_run("2.{{ loop.index }} {{ obj }}")
    set_thai_font(r, size_pt=16)
    p_obj_end = doc.add_paragraph()
    r = p_obj_end.add_run("{% endfor %}")
    set_thai_font(r, size_pt=16)

    # 3. Budget & Cost Breakdown Table (BOQ)
    p_b_h = doc.add_paragraph()
    r = p_b_h.add_run("3. วงเงินงบประมาณและการแจกแจงค่าใช้จ่าย (Cost Breakdown)")
    set_thai_font(r, size_pt=16, bold=True)
    
    p_b_intro = doc.add_paragraph()
    p_b_intro.paragraph_format.first_line_indent = Inches(0.5)
    r = p_b_intro.add_run("โครงการนี้มีวงเงินงบประมาณทั้งสิ้น {{ '{:,.2f}'.format(budget) }} บาท โดยมีรายละเอียดการแจกแจงค่าใช้จ่ายดังตารางต่อไปนี้:")
    set_thai_font(r, size_pt=16)

    # Add Dynamic Table for Budget
    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = table.rows[0].cells
    headers = ["ลำดับ", "รายการ", "จำนวน", "หน่วย", "ราคาต่อหน่วย (บาท)", "จำนวนเงินรวม (บาท)"]
    widths = [Inches(0.6), Inches(2.5), Inches(0.7), Inches(0.8), Inches(1.3), Inches(1.3)]
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_margins(hdr_cells[i])
        for p in hdr_cells[i].paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                set_thai_font(r, size_pt=14, bold=True)
        shd = parse_xml(r'<w:shd {} w:fill="E8EEF5"/>'.format(nsdecls('w')))
        hdr_cells[i]._element.get_or_add_tcPr().append(shd)

    # 1. Loop start row
    r_start = table.add_row()
    r_start.cells[0].text = "{%tr for item in budget_breakdown %}"

    # 2. Data row
    r_data = table.add_row()
    data_cells = r_data.cells
    data_cells[0].text = "{{ loop.index }}"
    data_cells[1].text = "{{ item.name }}"
    data_cells[2].text = "{{ item.qty }}"
    data_cells[3].text = "{{ item.unit }}"
    data_cells[4].text = "{{ '{:,.2f}'.format(item.unit_price) }}"
    data_cells[5].text = "{{ '{:,.2f}'.format(item.total_price) }}"

    for i in range(6):
        set_cell_margins(data_cells[i])
        for p in data_cells[i].paragraphs:
            if i in [0, 2, 3]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif i in [4, 5]:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for r in p.runs:
                set_thai_font(r, size_pt=14)

    # 3. Loop end row
    r_end = table.add_row()
    r_end.cells[0].text = "{%tr endfor %}"

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 4. Vendor Qualifications
    p_qual_h = doc.add_paragraph()
    r = p_qual_h.add_run("4. คุณสมบัติของผู้ยื่นข้อเสนอ")
    set_thai_font(r, size_pt=16, bold=True)
    p_q_loop = doc.add_paragraph()
    r = p_q_loop.add_run("{% for qual in vendor_qualifications %}")
    set_thai_font(r, size_pt=16)
    p_q_item = doc.add_paragraph()
    p_q_item.paragraph_format.first_line_indent = Inches(0.5)
    r = p_q_item.add_run("4.{{ loop.index }} {{ qual }}")
    set_thai_font(r, size_pt=16)
    p_q_end = doc.add_paragraph()
    r = p_q_end.add_run("{% endfor %}")
    set_thai_font(r, size_pt=16)

    # 5. Scope of Work
    p_sow_h = doc.add_paragraph()
    r = p_sow_h.add_run("5. ขอบเขตของงานและข้อกำหนดเฉพาะ (Scope of Work)")
    set_thai_font(r, size_pt=16, bold=True)
    p_sow_loop = doc.add_paragraph()
    r = p_sow_loop.add_run("{% for sow in scope_of_work %}")
    set_thai_font(r, size_pt=16)
    p_sow_item = doc.add_paragraph()
    p_sow_item.paragraph_format.first_line_indent = Inches(0.5)
    r = p_sow_item.add_run("5.{{ loop.index }} {{ sow }}")
    set_thai_font(r, size_pt=16)
    p_sow_end = doc.add_paragraph()
    r = p_sow_end.add_run("{% endfor %}")
    set_thai_font(r, size_pt=16)

    # 6. Deliverables & Payments Table
    p_deliv_h = doc.add_paragraph()
    r = p_deliv_h.add_run("6. ระยะเวลาดำเนินงาน การส่งมอบงาน และการจ่ายเงิน")
    set_thai_font(r, size_pt=16, bold=True)
    
    p_dur = doc.add_paragraph()
    p_dur.paragraph_format.first_line_indent = Inches(0.5)
    r = p_dur.add_run("ระยะเวลาดำเนินการทั้งสิ้น {{ duration_days }} วัน นับถัดจากวันลงนามในสัญญา โดยแบ่งการส่งมอบงานและการเบิกจ่ายเงินดังนี้:")
    set_thai_font(r, size_pt=16)

    p_d_loop = doc.add_paragraph()
    r = p_d_loop.add_run("{% for d in deliverables_and_payments %}")
    set_thai_font(r, size_pt=16)
    p_d_item = doc.add_paragraph()
    p_d_item.paragraph_format.first_line_indent = Inches(0.5)
    r = p_d_item.add_run("งวดที่ {{ loop.index }}: {{ d }}")
    set_thai_font(r, size_pt=16)
    p_d_end = doc.add_paragraph()
    r = p_d_end.add_run("{% endfor %}")
    set_thai_font(r, size_pt=16)

    # 7. Evaluation Criteria
    p_crit_h = doc.add_paragraph()
    r = p_crit_h.add_run("7. หลักเกณฑ์การพิจารณาคัดเลือกข้อเสนอ")
    set_thai_font(r, size_pt=16, bold=True)
    p_crit = doc.add_paragraph()
    p_crit.paragraph_format.first_line_indent = Inches(0.5)
    r = p_crit.add_run("{{ evaluation_criteria }}")
    set_thai_font(r, size_pt=16)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    print(f"Created Jinja TOR template (with Garuda & Budget Table): {output_path}")

def create_official_memo_template(output_path, garuda_path="app/assets/garuda.png"):
    """
    Creates an official Thai government internal memo (บันทึกข้อความ)
    strictly following Prime Minister's Office Saraban Regulations:
    - Garuda emblem (1.5 cm) placed top-left.
    - Large 'บันทึกข้อความ' header centered.
    - Standard metadata fields: ส่วนราชการ, ที่, วันที่, เรื่อง, เรียน.
    - Clear structured body paragraphs.
    """
    doc = docx.Document()
    for s in doc.sections:
        s.top_margin = Inches(0.98)     # ~2.5 cm
        s.bottom_margin = Inches(0.79)  # ~2.0 cm
        s.left_margin = Inches(1.18)    # ~3.0 cm
        s.right_margin = Inches(0.79)   # ~2.0 cm

    # Top header table (Garuda on left 1.5 cm, Title centered)
    top_table = doc.add_table(rows=1, cols=2)
    top_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_left, c_right = top_table.rows[0].cells
    c_left.width = Inches(1.2)
    c_right.width = Inches(5.5)

    if os.path.exists(garuda_path):
        p_img = c_left.paragraphs[0]
        p_img.add_run().add_picture(garuda_path, width=Inches(0.59)) # 1.5 cm
    
    p_memo_title = c_right.paragraphs[0]
    p_memo_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_memo_title.add_run("บันทึกข้อความ\n")
    set_thai_font(r, size_pt=24, bold=True)

    # Metadata Paragraphs
    p_dept = doc.add_paragraph()
    r = p_dept.add_run("ส่วนราชการ: ")
    set_thai_font(r, size_pt=16, bold=True)
    r = p_dept.add_run("{{ agency_name }} {{ department_sub | default('') }}\n")
    set_thai_font(r, size_pt=16)

    p_num_date = doc.add_paragraph()
    r = p_num_date.add_run("ที่: ")
    set_thai_font(r, size_pt=16, bold=True)
    r = p_num_date.add_run("{{ doc_number }}")
    set_thai_font(r, size_pt=16)
    r = p_num_date.add_run("                       วันที่: ")
    set_thai_font(r, size_pt=16, bold=True)
    r = p_num_date.add_run("{{ doc_date }}\n")
    set_thai_font(r, size_pt=16)

    p_subj = doc.add_paragraph()
    r = p_subj.add_run("เรื่อง: ")
    set_thai_font(r, size_pt=16, bold=True)
    r = p_subj.add_run("{{ subject }}\n")
    set_thai_font(r, size_pt=16, bold=True)

    p_to = doc.add_paragraph()
    r = p_to.add_run("เรียน: ")
    set_thai_font(r, size_pt=16, bold=True)
    r = p_to.add_run("{{ recipient }}\n")
    set_thai_font(r, size_pt=16)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 1. Background / Context
    p_b1 = doc.add_paragraph()
    p_b1.paragraph_format.first_line_indent = Inches(0.5)
    r = p_b1.add_run("{{ background_text }}")
    set_thai_font(r, size_pt=16)

    # 2. Key Facts / Considerations
    p_b2 = doc.add_paragraph()
    p_b2.paragraph_format.first_line_indent = Inches(0.5)
    r = p_b2.add_run("{{ considerations_text }}")
    set_thai_font(r, size_pt=16)

    # Signoff
    p_signoff = doc.add_paragraph()
    p_signoff.paragraph_format.first_line_indent = Inches(0.5)
    p_signoff.paragraph_format.space_before = Pt(12)
    r = p_signoff.add_run("จึงเรียนมาเพื่อโปรด{{ action_request | default('พิจารณาให้ความเห็นชอบ') }}")
    set_thai_font(r, size_pt=16)

    # Signature Block
    p_sig = doc.add_paragraph()
    p_sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_sig.paragraph_format.space_before = Pt(28)
    r = p_sig.add_run("({{ signer_name }})\n{{ signer_position }}")
    set_thai_font(r, size_pt=16)

    doc.save(output_path)
    print(f"Created Official Memo template (with Garuda 1.5cm): {output_path}")

if __name__ == '__main__':
    create_tor_template('app/templates/tor_template.docx')
    create_official_memo_template('app/templates/memo_template.docx')
