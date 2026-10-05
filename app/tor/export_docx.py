"""Render a TORResult to the .docx the user downloads.

Thai government document conventions: A4, TH Sarabun New 16 pt, margins top 2.5 / bottom 2 /
left 3 / right 2 cm, Thai-distributed justification, numbered chapters (1. / 1.1), BOQ and
payment tables with totals and the amount in Thai words, committee sign-off, centred page numbers.

Rendering is gated: if blocking findings are unacknowledged, export is refused unless the caller
asks for a draft, which is stamped "ฉบับร่าง" on every page.
"""
import re
from pathlib import Path
from typing import List, Optional

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.tor.procurement import METHOD_LABEL_TH
from app.tor.schemas import ChapterKind, DraftChapter, TORResult

FONT = "TH Sarabun New"
BODY_PT = 16
TABLE_PT = 14
EMBLEM_PATH = Path("app/assets/garuda.png")


class ExportBlocked(Exception):
    """Raised when unacknowledged blocking findings remain and a final export was requested."""


# ----------------- Thai line breaking -----------------
_THAI = re.compile(r"[฀-๿]")
_ZWSP = "​"


def breakable(text: str) -> str:
    """Insert zero-width spaces between Thai words so Word can wrap lines.

    Thai has no spaces between words; Word (without Thai proofing tools) then treats a whole
    phrase as one word and pushes it onto a new line or splits it mid-word. Applied only to the
    rendered .docx; the structured chapters keep the original text.
    """
    if not _THAI.search(text):
        return text
    from pythainlp.tokenize import word_tokenize
    tokens = word_tokenize(text, engine="newmm", keep_whitespace=True)
    out = [tokens[0]] if tokens else []
    for prev, tok in zip(tokens, tokens[1:]):
        if _THAI.search(prev[-1:]) and _THAI.search(tok[:1]):
            out.append(_ZWSP)
        out.append(tok)
    return "".join(out)


# ----------------- Thai baht text -----------------
_DIGITS = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_PLACES = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def _read_int(n: int, after_higher: bool = False) -> str:
    """after_higher: a higher group (ล้าน) precedes, so a trailing 1 reads เอ็ด (e.g. หนึ่งล้านเอ็ด)."""
    if n == 0:
        return ""
    if n >= 1_000_000:
        return _read_int(n // 1_000_000) + "ล้าน" + _read_int(n % 1_000_000, after_higher=True)
    out, s = "", str(n)
    for i, ch in enumerate(s):
        d, place = int(ch), len(s) - i - 1
        if d == 0:
            continue
        if place == 0 and d == 1 and (len(s) > 1 or after_higher):
            out += "เอ็ด"
        elif place == 1 and d == 2:
            out += "ยี่"
        elif place == 1 and d == 1:
            out += ""
        else:
            out += _DIGITS[d]
        out += _PLACES[place]
    return out


def baht_text(amount: float) -> str:
    """3500000.5 -> 'สามล้านห้าแสนบาทห้าสิบสตางค์'"""
    satang_total = round(amount * 100)
    baht, satang = divmod(satang_total, 100)
    words = (_read_int(baht) or "ศูนย์") + "บาท"
    return words + (_read_int(satang) + "สตางค์" if satang else "ถ้วน")


# ----------------- low-level formatting -----------------
def _set_run_font(run, size: float = BODY_PT, bold: bool = False, color: Optional[RGBColor] = None) -> None:
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), FONT)
    # Thai is a complex script: size and bold must also be set on the cs variants, placed right
    # after their non-cs siblings (rPr child order is schema-enforced; Word rejects misordered XML).
    if rpr.find(qn("w:szCs")) is None:
        sz_cs = OxmlElement("w:szCs")
        sz_cs.set(qn("w:val"), str(int(size * 2)))
        rpr.find(qn("w:sz")).addnext(sz_cs)
    if bold and rpr.find(qn("w:bCs")) is None:
        rpr.find(qn("w:b")).addnext(OxmlElement("w:bCs"))
    # Mark the run as Thai so Word applies its Thai word-breaking dictionary; without it a long
    # space-free Thai phrase is treated as one word and pushed whole onto the next line.
    if rpr.find(qn("w:lang")) is None:
        lang = OxmlElement("w:lang")  # last child of rPr in schema order
        lang.set(qn("w:val"), "th-TH")
        lang.set(qn("w:bidi"), "th-TH")
        rpr.append(lang)


def _thai_distribute(par) -> None:
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "thaiDistribute")
    par._p.get_or_add_pPr().append(jc)


def _para(doc_or_cell, text: str = "", size: float = BODY_PT, bold: bool = False,
          align=None, first_indent: Optional[float] = None, left_indent: Optional[float] = None,
          hanging: Optional[float] = None, space_after: float = 0, distribute: bool = False,
          color: Optional[RGBColor] = None):
    par = doc_or_cell.add_paragraph()
    pf = par.paragraph_format
    pf.space_before, pf.space_after, pf.line_spacing = Pt(0), Pt(space_after), 1.0
    if align is not None:
        par.alignment = align
    if distribute:
        _thai_distribute(par)
    if left_indent is not None:
        pf.left_indent = Cm(left_indent)
    if first_indent is not None:
        pf.first_line_indent = Cm(first_indent)
    if hanging is not None:
        pf.first_line_indent = Cm(-hanging)
        if left_indent is not None:
            pf.tab_stops.add_tab_stop(Cm(left_indent))
    if text:
        _set_run_font(par.add_run(breakable(text)), size, bold, color)
    return par


def _cell(cell, text: str, bold: bool = False, align=WD_ALIGN_PARAGRAPH.LEFT) -> None:
    cell.paragraphs[0].text = ""
    par = cell.paragraphs[0]
    par.alignment = align
    par.paragraph_format.space_after = Pt(0)
    _set_run_font(par.add_run(breakable(text)), TABLE_PT, bold)


def _fix_widths(table, widths_cm: List[float]) -> None:
    """Word ignores cell widths under autofit; pin a fixed layout so amounts don't wrap."""
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    for i, w in enumerate(widths_cm):
        table.columns[i].width = Cm(w)
        for cell in table.columns[i].cells:
            cell.width = Cm(w)


def _shade(cell, hex_fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _page_number_footer(section) -> None:
    par = section.footer.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(par.add_run("- "))
    run = par.add_run()
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    _set_run_font(run)
    _set_run_font(par.add_run(" -"))


def _money(x: float) -> str:
    return f"{x:,.2f}"


# ----------------- document sections -----------------
def _title_block(doc, result: TORResult, emblem: bool) -> None:
    req = result.request
    if emblem and EMBLEM_PATH.exists():
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(EMBLEM_PATH), height=Cm(3))
    _para(doc, "ร่างขอบเขตของงาน (Terms of Reference: TOR)", 20, True, WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, req.project_name, BODY_PT + 2, True, WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, req.agency_name, BODY_PT, False, WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, f"โดย{METHOD_LABEL_TH[result.report.procurement_method]}", BODY_PT, False,
          WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, "-" * 30, BODY_PT, False, WD_ALIGN_PARAGRAPH.CENTER, space_after=6)


def _boq_table(doc, ch: DraftChapter, budget: float) -> None:
    headers = ["ลำดับ", "รายการ", "จำนวน", "หน่วย", "ราคาต่อหน่วย (บาท)", "จำนวนเงิน (บาท)"]
    widths = [1.2, 6.0, 1.4, 1.4, 3.0, 3.0]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        _cell(table.rows[0].cells[i], h, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        _shade(table.rows[0].cells[i], "D9D9D9")
    R, C, L = WD_ALIGN_PARAGRAPH.RIGHT, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT
    for n, item in enumerate(ch.boq, 1):
        cells = table.add_row().cells
        for i, (val, al) in enumerate([(str(n), C), (item.name, L), (f"{item.qty:,}", C), (item.unit, C),
                                       (_money(item.unit_price), R), (_money(item.total_price), R)]):
            _cell(cells[i], val, align=al)
    total = round(sum(b.total_price for b in ch.boq), 2)
    row = table.add_row().cells
    merged = row[0].merge(row[4])
    _cell(merged, f"รวมทั้งสิ้น ({baht_text(total)})", bold=True, align=C)
    _cell(row[5], _money(total), bold=True, align=R)
    _fix_widths(table, widths)
    _para(doc, space_after=6)


def _payment_table(doc, ch: DraftChapter, budget: float) -> None:
    headers = ["งวดที่", "ร้อยละ", "จำนวนเงิน (บาท)", "เงื่อนไขการส่งมอบ", "กำหนดส่งมอบ"]
    widths = [1.3, 1.5, 3.0, 7.4, 2.8]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        _cell(table.rows[0].cells[i], h, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        _shade(table.rows[0].cells[i], "D9D9D9")
    R, C, L = WD_ALIGN_PARAGRAPH.RIGHT, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT
    allocated = 0.0
    for idx, inst in enumerate(ch.installments):
        last = idx == len(ch.installments) - 1
        amount = round(budget - allocated, 2) if last else round(budget * inst.percent / 100, 2)
        allocated = round(allocated + amount, 2)
        cells = table.add_row().cells
        for i, (val, al) in enumerate([(str(inst.no), C), (f"{inst.percent:g}", C), (_money(amount), R),
                                       (inst.deliverable, L), (f"ภายใน {inst.due_day} วัน", C)]):
            _cell(cells[i], val, align=al)
    _fix_widths(table, widths)
    _para(doc, "หมายเหตุ: กำหนดส่งมอบนับถัดจากวันลงนามในสัญญา", BODY_PT - 2, space_after=6)


def _chapter(doc, n: int, ch: DraftChapter, budget: float) -> None:
    _para(doc, f"{n}. {ch.title}", BODY_PT, True, space_after=2).paragraph_format.keep_with_next = True
    if ch.kind == ChapterKind.TEXT:
        blocks = [b.strip() for b in ch.text.split("\n") if b.strip()]
        if blocks and blocks[0].rstrip(":： ") == ch.title.strip():  # drafter repeated the heading
            blocks = blocks[1:]
        for block in blocks:
            _para(doc, block, first_indent=2.5, space_after=4)
    elif ch.kind == ChapterKind.LIST:
        for i, item in enumerate(ch.items, 1):
            _para(doc, f"{n}.{i}\t{item}", left_indent=2.25, hanging=1.0, space_after=2)
    elif ch.kind == ChapterKind.BOQ:
        _para(doc, f"วงเงินงบประมาณ {_money(budget)} บาท ({baht_text(budget)}) "
                   f"รวมภาษีมูลค่าเพิ่มและค่าใช้จ่ายอื่นทั้งปวงแล้ว โดยมีรายละเอียดดังนี้",
              first_indent=2.5, space_after=4)
        _boq_table(doc, ch, budget)
    elif ch.kind == ChapterKind.PAYMENT_SCHEDULE:
        _para(doc, "หน่วยงานจะจ่ายเงินค่าจ้างตามงวดงาน เมื่อคณะกรรมการตรวจรับพัสดุได้ตรวจรับงานแต่ละงวดเรียบร้อยแล้ว ดังนี้",
              first_indent=2.5, space_after=4)
        _payment_table(doc, ch, budget)
    _para(doc, space_after=4)


def _signatures(doc, committee: List[str]) -> None:
    roles = ["ประธานกรรมการ", "กรรมการ", "กรรมการ"]
    members = committee or [""] * len(roles)
    _para(doc, "คณะกรรมการจัดทำร่างขอบเขตของงาน", BODY_PT, True, WD_ALIGN_PARAGRAPH.CENTER, space_after=12)
    for i, name in enumerate(members):
        role = roles[i] if i < len(roles) else "กรรมการ"
        _para(doc, "ลงชื่อ ......................................................... " + role,
              align=WD_ALIGN_PARAGRAPH.CENTER)
        _para(doc, f"({name or ' ' * 50})", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)


# ----------------- entry point -----------------
def render_tor_docx(result: TORResult, out_path: str, draft: bool = False, emblem: bool = True) -> Path:
    """Write the .docx. Raises ExportBlocked when unacknowledged blocking findings remain and
    draft=False; with draft=True the document is stamped as a draft on every page."""
    pending = result.report.unacknowledged_blocking
    if pending and not draft:
        raise ExportBlocked(f"{len(pending)} blocking finding(s) not resolved or acknowledged: "
                            + ", ".join(f.key for f in pending))

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(2.5), Cm(2.0)
    sec.left_margin, sec.right_margin = Cm(3.0), Cm(2.0)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(BODY_PT)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), FONT)

    if draft:
        hp = sec.header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_run_font(hp.add_run(f"ฉบับร่าง (ยังมีประเด็นที่ไม่ผ่านการตรวจสอบ {len(pending)} รายการ)"),
                      14, True, RGBColor(0xC0, 0x00, 0x00))
    _page_number_footer(sec)

    _title_block(doc, result, emblem)
    for n, ch in enumerate(result.chapters, 1):
        _chapter(doc, n, ch, result.request.budget)
    _signatures(doc, result.request.extra_context.get("committee", []))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    return out
