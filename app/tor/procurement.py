"""Deterministic procurement-method resolution. Never delegated to the LLM: thresholds are law."""
from typing import List, Tuple

from app.tor.schemas import TORRequest, ProcurementMethod, ProcurementType

# Unverified until the กฎกระทรวงกำหนดวงเงินฯ ๒๕๖๐ is in the corpus; see SPECIFIC_METHOD_BUDGET_CAP.
SPECIFIC_METHOD_MAX_BUDGET = 500_000


def resolve_method(req: TORRequest) -> Tuple[ProcurementMethod, List[str]]:
    """Returns (method, assumptions). Upstream-provided method always wins; rules still check it."""
    if req.procurement_method:
        return req.procurement_method, [f"ใช้วิธี {req.procurement_method.value} ตามที่ระบบต้นทางกำหนด"]

    assumptions: List[str] = []
    if req.procurement_type in (ProcurementType.CONSULTING, ProcurementType.DESIGN_SUPERVISION):
        assumptions.append(
            "งานจ้างที่ปรึกษา/ออกแบบควบคุมงานมีวิธีเฉพาะของหมวดนั้น ระบบตั้งค่าเริ่มต้นเป็นประกาศเชิญชวนทั่วไป "
            "โปรดให้เจ้าหน้าที่พัสดุยืนยัน"
        )
        return ProcurementMethod.GENERAL_INVITATION, assumptions

    if req.budget <= SPECIFIC_METHOD_MAX_BUDGET:
        assumptions.append(
            f"วงเงิน {req.budget:,.2f} บาท ไม่เกิน {SPECIFIC_METHOD_MAX_BUDGET:,} บาท จึงเลือกวิธีเฉพาะเจาะจง "
            "(เกณฑ์วงเงินยังรอผู้เชี่ยวชาญยืนยัน)"
        )
        return ProcurementMethod.SPECIFIC, assumptions

    assumptions.append(
        "วงเงินเกินเกณฑ์วิธีเฉพาะเจาะจง จึงเลือกวิธีประกวดราคาอิเล็กทรอนิกส์ "
        "(หากพัสดุอยู่ในระบบ e-catalog ควรใช้วิธีตลาดอิเล็กทรอนิกส์แทน)"
    )
    return ProcurementMethod.E_BIDDING, assumptions


METHOD_LABEL_TH = {
    ProcurementMethod.E_MARKET: "วิธีตลาดอิเล็กทรอนิกส์ (e-market)",
    ProcurementMethod.E_BIDDING: "วิธีประกวดราคาอิเล็กทรอนิกส์ (e-bidding)",
    ProcurementMethod.SELECTION: "วิธีคัดเลือก",
    ProcurementMethod.SPECIFIC: "วิธีเฉพาะเจาะจง",
    ProcurementMethod.GENERAL_INVITATION: "วิธีประกาศเชิญชวนทั่วไป",
}

TYPE_LABEL_TH = {
    ProcurementType.GOODS: "ซื้อ",
    ProcurementType.SERVICES: "จ้างทั่วไป",
    ProcurementType.CONSULTING: "จ้างที่ปรึกษา",
    ProcurementType.DESIGN_SUPERVISION: "จ้างออกแบบหรือควบคุมงานก่อสร้าง",
    ProcurementType.CONSTRUCTION: "จ้างก่อสร้าง",
}
