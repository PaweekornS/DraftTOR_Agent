from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class DocumentType(str, Enum):
    MEMO = "MEMO"
    MEETING_AGENDA = "MEETING_AGENDA"
    LEAVE_REQUEST = "LEAVE_REQUEST"

# ----------------- MEMO SCHEMAS -----------------
class MemoInputRequest(BaseModel):
    agency_name: str = Field(..., description="ส่วนราชการ / กระทรวง กรม")
    department_sub: Optional[str] = Field("", description="กอง / กลุ่มงาน / ฝ่าย")
    doc_number: str = Field("ที่ กค ๐๔๐๕/...", description="เลขที่หนังสือราชการ")
    doc_date: str = Field("๒๖ กันยายน ๒๕๖๙", description="วันที่ในเอกสารราชการ")
    subject: str = Field(..., description="เรื่อง")
    recipient: str = Field(..., description="เรียน (ตำแหน่งผู้รับ เช่น อธิบดี, ปลัดกระทรวง)")
    raw_context: str = Field(..., description="เหตุผลความจำเป็นและข้อเท็จจริงที่ต้องการเสนอ")
    action_request: str = Field("พิจารณาให้ความเห็นชอบ", description="คำขอท้ายเรื่อง (พิจารณาอนุมัติ/เห็นชอบ/ลงนาม)")
    signer_name: str = Field(..., description="ชื่อผู้ลงนาม")
    signer_position: str = Field(..., description="ตำแหน่งผู้ลงนาม")

class MemoDraftPayload(BaseModel):
    agency_name: str
    department_sub: str = ""
    doc_number: str
    doc_date: str
    subject: str
    recipient: str
    background_text: str = Field(..., description="ความเป็นมา/ต้นเรื่อง")
    considerations_text: str = Field(..., description="ข้อเท็จจริงและข้อพิจารณา")
    action_request: str
    signer_name: str
    signer_position: str

# ----------------- MEETING AGENDA SCHEMAS -----------------
class MeetingAgendaRequest(BaseModel):
    committee_name: str = Field(..., description="ชื่อคณะกรรมการหรือการประชุม")
    meeting_no: int = Field(1, description="ครั้งที่")
    meeting_year: int = Field(2569, description="ปี พ.ศ.")
    meeting_date: str = Field("วันศุกร์ที่ ๒๖ กันยายน ๒๕๖๙", description="วัน เดือน ปี")
    meeting_time: str = Field("๐๙.๓๐ - ๑๒.๐๐", description="เวลา")
    meeting_location: str = Field("ห้องประชุม ๑ อาคาร...", description="สถานที่")
    raw_agenda_topics: str = Field(..., description="ประเด็นหรือวาระที่ต้องการบรรจุในการประชุม")

class MeetingAgendaPayload(BaseModel):
    committee_name: str
    meeting_no: int
    meeting_year: int
    meeting_date: str
    meeting_time: str
    meeting_location: str
    agenda_1_chairman_notes: str
    agenda_2_previous_minutes: str
    agenda_3_matters_to_inform: List[str]
    agenda_4_matters_for_consideration: List[str]
    agenda_5_other_matters: str = "ไม่มี"
