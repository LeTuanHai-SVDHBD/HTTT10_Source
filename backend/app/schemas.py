"""DTO contract 1.0. Không có router, truy vấn DB hay xử lý SMTP ở mô-đun này."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import UUID
from pydantic import (
    BaseModel, ConfigDict, Field, AwareDatetime, EmailStr, SecretStr,
    BeforeValidator, AfterValidator, model_validator, create_model, RootModel,
)

def require_datetime(value):
    if not isinstance(value,(str,datetime)):
        raise ValueError('Phải dùng chuỗi RFC3339 có múi giờ, không dùng timestamp số')
    return value
def utc(value):return value.astimezone(timezone.utc)
UtcDatetime=Annotated[AwareDatetime,BeforeValidator(require_datetime),AfterValidator(utc)]
Version=Annotated[int,Field(strict=True,ge=1)]
NonBlank=Annotated[str,Field(min_length=1,max_length=1000,pattern=r'\S')]
Title=Annotated[str,Field(min_length=1,max_length=255,pattern=r'\S')]
TimeText=Annotated[str,Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')]
Role=Literal['EMPLOYEE','APPROVER','ADMIN']
Password=Annotated[SecretStr,Field(min_length=12,max_length=128)]

class DTO(BaseModel):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)

def unique(values,label):
    if len(values)!=len(set(values)):raise ValueError(label+' không được trùng')

class ParticipantInput(DTO):
    user_id:UUID
    is_required:bool=Field(strict=True)

class TimeRange(DTO):
    starts_at:UtcDatetime
    ends_at:UtcDatetime
    @model_validator(mode='after')
    def check_range(self):
        if self.starts_at>=self.ends_at:raise ValueError('Bắt đầu phải trước kết thúc')
        return self

class MeetingInput(TimeRange):
    kind:Literal['MEETING']
    title:Title
    description:Annotated[str,Field(max_length=10000)]=''
    room_id:UUID
    chair_user_id:UUID
    participants:Annotated[list[ParticipantInput],Field(min_length=1)]
    @model_validator(mode='after')
    def check_participants(self):
        unique([p.user_id for p in self.participants],'Người tham gia')
        if not any(p.user_id==self.chair_user_id and p.is_required for p in self.participants):
            raise ValueError('Chủ trì phải nằm trong danh sách bắt buộc')
        return self

class WorkInput(TimeRange):
    kind:Literal['WORK']
    title:Title
    description:Annotated[str,Field(max_length=10000)]=''
    department_id:UUID
    work_location:Annotated[str,Field(min_length=1,max_length=500,pattern=r'\S')]
    work_context:Literal['INTERNAL','EXTERNAL']
    participant_user_ids:Annotated[list[UUID],Field(min_length=1)]
    @model_validator(mode='after')
    def check_participants(self):
        unique(self.participant_user_ids,'Người đi công tác');return self

Candidate=Annotated[Union[MeetingInput,WorkInput],Field(discriminator='kind')]

class WarningAcknowledgement(DTO):
    warning_acknowledgement_token:Annotated[str,Field(min_length=1,max_length=512)]|None=None

class SubmitMeeting(WarningAcknowledgement):candidate:MeetingInput
class SubmitWork(WarningAcknowledgement):candidate:WorkInput
class AvailabilityCheck(DTO):
    candidate:Candidate
    exclude_schedule_id:UUID|None=None

class ChangeRequest(WarningAcknowledgement):
    expected_schedule_version:Version
    base_revision_id:UUID
    candidate:Candidate

class CancellationRequest(DTO):
    expected_schedule_version:Version
    reason:NonBlank

class ProposalDecision(WarningAcknowledgement):
    expected_schedule_version:Version
    expected_proposal_version:Version
    decision:Literal['APPROVE','REJECT']
    reason:NonBlank|None=None
    @model_validator(mode='after')
    def reject_reason(self):
        if self.decision=='REJECT' and self.reason is None:raise ValueError('Từ chối cần lý do')
        return self

class ProposalWithdrawal(DTO):
    expected_schedule_version:Version
    expected_proposal_version:Version
    reason:NonBlank|None=None

class LoginInput(DTO):
    email:EmailStr
    password:Annotated[SecretStr,Field(min_length=1,max_length=128)]

class PasswordChange(DTO):
    current_password:Annotated[SecretStr,Field(min_length=1,max_length=128)]
    new_password:Password
    confirm_password:Password
    @model_validator(mode='after')
    def match(self):
        if self.new_password.get_secret_value()!=self.confirm_password.get_secret_value():raise ValueError('Xác nhận mật khẩu không khớp')
        if self.new_password.get_secret_value()==self.current_password.get_secret_value():raise ValueError('Mật khẩu mới phải khác mật khẩu hiện tại')
        return self

class UserRef(DTO):
    id:UUID
    employee_code:Annotated[str,Field(min_length=1,max_length=32)]
    full_name:Annotated[str,Field(min_length=1,max_length=150)]
    department_id:UUID

class CurrentUser(UserRef):
    email:EmailStr
    roles:list[Role]
    room_scope_ids:list[UUID]
    department_scope_ids:list[UUID]
    must_change_password:bool

class TokenResponse(DTO):
    access_token:str
    token_type:Literal['bearer']
    expires_in:Annotated[int,Field(gt=0)]
    must_change_password:bool

class UserFields(DTO):
    employee_code:Annotated[str,Field(min_length=1,max_length=32,pattern=r'\S')]
    full_name:Annotated[str,Field(min_length=1,max_length=150,pattern=r'\S')]
    email:EmailStr
    department_id:UUID
    status:Literal['ACTIVE','LOCKED']
    roles:Annotated[list[Role],Field(min_length=1)]
    @model_validator(mode='after')
    def unique_roles(self):unique(self.roles,'Vai trò');return self

class UserCreate(UserFields):temporary_password:Password
class UserUpdate(UserFields):expected_user_version:Version
class UserAdminView(UserFields):
    id:UUID
    row_version:Version
    must_change_password:bool
class PasswordReset(DTO):
    expected_user_version:Version
    new_temporary_password:Password

class DepartmentFields(DTO):
    code:Annotated[str,Field(min_length=1,max_length=32,pattern=r'\S')]
    name:Annotated[str,Field(min_length=1,max_length=150,pattern=r'\S')]
    accepts_new_requests:bool=Field(strict=True)
class DepartmentCreate(DepartmentFields):pass
class DepartmentUpdate(DepartmentFields):expected_department_version:Version
class DepartmentView(DepartmentFields):
    id:UUID
    row_version:Version

class Equipment(DTO):
    equipment_code:Annotated[str,Field(min_length=1,max_length=40,pattern=r'\S')]
    display_name:Annotated[str,Field(min_length=1,max_length=120,pattern=r'\S')]
    quantity:Annotated[int,Field(strict=True,ge=1,le=65535)]

class ServiceWindow(DTO):
    start_time:TimeText
    end_time:TimeText
    @model_validator(mode='after')
    def order(self):
        if self.start_time>=self.end_time:raise ValueError('Khoảng phục vụ phải tăng trong cùng ngày')
        return self

def non_overlapping(windows):
    ordered=sorted(windows,key=lambda w:w.start_time)
    if any(a.end_time>b.start_time for a,b in zip(ordered,ordered[1:])):raise ValueError('Khoảng phục vụ không được chồng nhau')

class WeeklyWindow(ServiceWindow):weekday:Annotated[int,Field(strict=True,ge=1,le=7)]
class CalendarDay(DTO):
    local_date:Annotated[str,Field(pattern=r'^\d{4}-\d{2}-\d{2}$')]
    is_closed:bool=Field(strict=True)
    reason:Annotated[str,Field(min_length=1,max_length=255,pattern=r'\S')]
    windows:list[ServiceWindow]
    @model_validator(mode='after')
    def valid_day(self):
        datetime.strptime(self.local_date,'%Y-%m-%d')
        if self.is_closed and self.windows:raise ValueError('Ngày nghỉ không có khoảng mở')
        if not self.is_closed and not self.windows:raise ValueError('Ngoại lệ mở phải có khoảng phục vụ')
        non_overlapping(self.windows);return self

class RoomPolicyDefinition(DTO):
    effective_from:UtcDatetime
    capacity:Annotated[int,Field(strict=True,ge=1,le=65535)]
    buffer_minutes:Annotated[int,Field(strict=True,ge=0,le=65535)]=15
    weekly_windows:list[WeeklyWindow]
    calendar_days:list[CalendarDay]
    @model_validator(mode='after')
    def windows(self):
        for day in range(1,8):non_overlapping([w for w in self.weekly_windows if w.weekday==day])
        unique([d.local_date for d in self.calendar_days],'Ngày ngoại lệ');return self

class RoomPolicyCreate(RoomPolicyDefinition):expected_room_version:Version
class RoomPolicyView(RoomPolicyDefinition):
    id:UUID
    room_id:UUID

class RoomFields(DTO):
    code:Annotated[str,Field(min_length=1,max_length=32,pattern=r'\S')]
    name:Annotated[str,Field(min_length=1,max_length=150,pattern=r'\S')]
    location:Annotated[str,Field(min_length=1,max_length=255,pattern=r'\S')]
    accepts_new_requests:bool=Field(strict=True)
    equipment:list[Equipment]
    @model_validator(mode='after')
    def unique_equipment(self):unique([e.equipment_code for e in self.equipment],'Mã thiết bị');return self
class RoomCreate(RoomFields):initial_policy:RoomPolicyDefinition
class RoomUpdate(RoomFields):expected_room_version:Version
class RoomView(RoomFields):
    id:UUID
    row_version:Version
    effective_policy:RoomPolicyView|None
class RoomApproversUpdate(DTO):
    expected_room_version:Version
    approver_user_ids:list[UUID]
    @model_validator(mode='after')
    def names(self):unique(self.approver_user_ids,'Người duyệt');return self
class DepartmentApproversUpdate(DTO):
    expected_department_version:Version
    approver_user_ids:list[UUID]
    @model_validator(mode='after')
    def names(self):unique(self.approver_user_ids,'Người duyệt');return self
class RoomApproversView(DTO):
    pending_proposal_count:Annotated[int,Field(ge=0)]=0
    room_id:UUID
    room_version:Version
    approvers:list[UserRef]
class DepartmentApproversView(DTO):
    pending_proposal_count:Annotated[int,Field(ge=0)]=0
    department_id:UUID
    department_version:Version
    approvers:list[UserRef]

class SafeWarning(DTO):
    code:Literal['OPTIONAL_PARTICIPANT_BUSY','PENDING_ROOM_REQUEST','PENDING_PERSON_REQUEST']
    resource_type:Literal['ROOM','PERSON']
    resource_id:UUID
    starts_at:UtcDatetime|None=None
    ends_at:UtcDatetime|None=None
    message:str
class SafeConflict(DTO):
    code:Literal['ROOM_BUSY','REQUIRED_PERSON_BUSY','ROOM_CONFIG_INVALID']
    resource_type:Literal['ROOM','PERSON']
    resource_id:UUID
    starts_at:UtcDatetime|None=None
    ends_at:UtcDatetime|None=None
    message:str
class AvailabilityResult(DTO):
    checked_at:UtcDatetime
    holds_resources:Literal[False]
    bookable:bool
    conflicts:list[SafeConflict]
    warnings:list[SafeWarning]
    warning_acknowledgement_token:str|None=None
class RoomAvailabilityItem(DTO):
    room:RoomView
    capacity_at_requested_start:Annotated[int,Field(ge=1)]
    buffer_minutes_at_requested_start:Annotated[int,Field(ge=0)]
    warnings:list[SafeWarning]
class FieldError(DTO):
    path:str
    code:str
class ErrorInfo(DTO):
    code:str
    message:str
    field_errors:list[FieldError]=Field(default_factory=list)
    conflicts:list[SafeConflict]=Field(default_factory=list)
    warnings:list[SafeWarning]=Field(default_factory=list)
    warning_acknowledgement_token:str|None=None
    expiration_committed:bool=False
class ApiError(DTO):
    request_id:UUID
    error:ErrorInfo

class ParticipantView(DTO):
    user:UserRef
    is_required:bool
class RevisionFields(TimeRange):
    id:UUID
    schedule_id:UUID
    revision_no:Annotated[int,Field(ge=1)]
    title:Title
    description:str
    participants:list[ParticipantView]
class MeetingRevision(RevisionFields):
    kind:Literal['MEETING']
    room_id:UUID
    chair_user_id:UUID
class WorkRevision(RevisionFields):
    kind:Literal['WORK']
    department_id:UUID
    work_location:str
    work_context:Literal['INTERNAL','EXTERNAL']
Revision=Annotated[Union[MeetingRevision,WorkRevision],Field(discriminator='kind')]
class RevisionView(RootModel[Revision]):pass

class BusySchedule(TimeRange):
    visibility:Literal['BUSY_ONLY']
    room_id:UUID|None=None
    blocked_until:UtcDatetime|None=None
class CalendarBusyEntry(TimeRange):
    visibility:Literal['BUSY_ONLY']
    entry_key:str
    busy_type:Literal['BUSY','BUFFER']
    room_id:UUID|None=None
class CalendarDetailEntry(TimeRange):
    visibility:Literal['DETAIL']
    entry_key:str
    schedule_id:UUID
    revision_id:UUID
    kind:Literal['MEETING','WORK']
    title:Title
    room_id:UUID|None=None
CalendarEntry=Annotated[Union[CalendarBusyEntry,CalendarDetailEntry],Field(discriminator='visibility')]

class ProposalSummary(DTO):
    id:UUID
    schedule_id:UUID
    kind:Literal['CREATE','CHANGE','CANCEL']
    schedule_kind:Literal['MEETING','WORK']
    title:Title
    status:Literal['PENDING','APPROVED','REJECTED','WITHDRAWN','EXPIRED']
    row_version:Version
    expires_at:UtcDatetime
    created_at:UtcDatetime
class BaseComparison(TimeRange):
    revision_id:UUID
    room_id:UUID|None=None
    department_id:UUID|None=None
    changed_fields:list[Literal['title','description','starts_at','ends_at','room_id','chair_user_id','participants','department_id','work_location','work_context']]
class MailSummary(DTO):
    pending:Annotated[int,Field(ge=0)]
    smtp_accepted:Annotated[int,Field(ge=0)]
    failed:Annotated[int,Field(ge=0)]
    skipped:Annotated[int,Field(ge=0)]
class ProposalDetail(ProposalSummary):
    schedule_version:Version
    submitted_by:UserRef
    candidate:Revision|None
    base_comparison:BaseComparison|None
    resolved_by:UserRef|None
    resolved_at:UtcDatetime|None
    reason:str|None
    allowed_actions:list[Literal['APPROVE','REJECT','WITHDRAW']]
    email_summary:MailSummary|None=None
class CancellationView(DTO):
    cancelled_at:UtcDatetime
    cancelled_by:UserRef
    reason:str
class ScheduleDetail(DTO):
    visibility:Literal['DETAIL']
    id:UUID
    kind:Literal['MEETING','WORK']
    row_version:Version
    lifecycle:Literal['UNCONFIRMED','ACTIVE','CANCELLED']
    created_by:UserRef
    current_revision:Revision|None
    visible_proposals:list[ProposalSummary]
    cancellation:CancellationView|None
    allowed_actions:list[Literal['REQUEST_CHANGE','CANCEL_MEETING','REQUEST_WORK_CANCELLATION','MANAGE_DOCUMENTS']]
class ScheduleView(RootModel[Annotated[Union[BusySchedule,ScheduleDetail],Field(discriminator='visibility')]]):pass
class ScheduleSummary(TimeRange):
    id:UUID
    visible_revision_id:UUID
    kind:Literal['MEETING','WORK']
    title:Title
    lifecycle:Literal['UNCONFIRMED','ACTIVE','CANCELLED']
    is_effective_revision:bool
class CommandReceipt(DTO):
    committed:Literal[True]
    schedule_id:UUID
    proposal_id:UUID|None

class DocumentUploadMetadata(DTO):
    context_revision_id:UUID
    display_name:Annotated[str,Field(min_length=1,max_length=255,pattern=r'\S')]
class DocumentVersionUpload(DTO):
    context_revision_id:UUID
    expected_latest_version_id:UUID
class DocumentHide(DTO):
    expected_latest_version_id:UUID
    reason:Annotated[str,Field(min_length=1,max_length=500,pattern=r'\S')]
class DocumentVersionView(DTO):
    id:UUID
    document_id:UUID
    context_revision_id:UUID
    version_no:Annotated[int,Field(ge=1)]
    original_filename:Annotated[str,Field(max_length=255)]
    extension:Literal['pdf','docx','pptx','xlsx','jpg','jpeg','png']
    mime_type:str
    size_bytes:Annotated[int,Field(ge=1,le=20971520)]
    uploaded_by:UserRef
    created_at:UtcDatetime
class DocumentView(DTO):
    id:UUID
    display_name:str=Field(description="Tên được phép trong ngữ cảnh đọc; dùng tên version an toàn khi cần, không lấy tên mới ngoài phạm vi")
    context_revision_id:UUID
    is_hidden:bool
    versions:list[DocumentVersionView]
    allowed_actions:list[Literal['UPLOAD_VERSION','HIDE']]

class AuditItem(DTO):
    id:UUID
    action:str
    actor:UserRef|None
    revision_id:UUID|None
    occurred_at:UtcDatetime
    summary:str

class UsageMetrics(DTO):
    confirmed_count:Annotated[int,Field(ge=0)]
    cancelled_count:Annotated[int,Field(ge=0)]
    meeting_hours:Annotated[float,Field(ge=0)]
    buffer_hours:Annotated[float,Field(ge=0)]
    service_hours:Annotated[float,Field(ge=0)]
    planned_rate_percent:Annotated[float,Field(ge=0,le=100)]|None
    @model_validator(mode='after')
    def denominator(self):
        if self.service_hours==0 and self.planned_rate_percent is not None:raise ValueError('Mẫu số 0 phải hiển thị Không áp dụng')
        return self
class RoomUsage(UsageMetrics):room_id:UUID
class UsageReport(DTO):
    period_from:UtcDatetime
    period_to:UtcDatetime
    generated_at:UtcDatetime
    basis:Literal['PLANNED_BOOKINGS']
    rooms:list[RoomUsage]
    total:UsageMetrics
class HealthView(DTO):status:Literal['ok','ready']

def page(name,item):
    cls=create_model(name,__base__=DTO,items=(list[item],...),page=(Annotated[int,Field(ge=1)],...),page_size=(Annotated[int,Field(ge=1,le=100)],...),total=(Annotated[int,Field(ge=0)],...))
    cls.__module__=__name__;return cls
UserDirectoryPage=page('UserDirectoryPage',UserRef)
UserAdminPage=page('UserAdminPage',UserAdminView)
DepartmentPage=page('DepartmentPage',DepartmentView)
RoomPage=page('RoomPage',RoomView)
RoomPolicyPage=page('RoomPolicyPage',RoomPolicyView)
RoomAvailabilityPage=page('RoomAvailabilityPage',RoomAvailabilityItem)
CalendarPage=page('CalendarPage',CalendarEntry)
SchedulePage=page('SchedulePage',ScheduleSummary)
ProposalPage=page('ProposalPage',ProposalSummary)
RevisionPage=page('RevisionPage',Revision)
DocumentPage=page('DocumentPage',DocumentView)
DocumentVersionPage=page('DocumentVersionPage',DocumentVersionView)
AuditPage=page('AuditPage',AuditItem)

def exported_models():
    return {v.__name__:v for v in globals().values() if isinstance(v,type) and issubclass(v,BaseModel) and v.__module__==__name__ and v is not DTO}
