import React, { useEffect, useState } from "react";
import { stamp, commandKey, localInput, allPages } from "./api";

const statusNames = {
  PENDING: "Chờ duyệt",
  APPROVED: "Đã duyệt",
  REJECTED: "Bị từ chối",
  WITHDRAWN: "Đã rút",
  EXPIRED: "Hết hạn",
};
const lifecycleNames = {
  UNCONFIRMED: "Chưa xác nhận",
  ACTIVE: "Đã xác nhận",
  CANCELLED: "Đã hủy",
};
const modes = ["new_schedule", "my_proposals", "review", "my_schedules"];
const initialDraft = (user) => ({
  kind: "MEETING",
  title: "",
  description: "",
  start: "",
  end: "",
  room_id: "",
  chair_user_id: user.id,
  participants: [{ user_id: user.id, is_required: true }],
  work_location: "",
  work_context: "EXTERNAL",
});

function Pager({ value, change, busy }) {
  if (!value || value.total <= value.page_size) return null;
  return (
    <div className="pager">
      <button
        className="secondary"
        disabled={busy || value.page === 1}
        onClick={() => change(value.page - 1)}
      >
        ← Trước
      </button>
      <span>
        Trang {value.page} / {Math.ceil(value.total / value.page_size)}
      </span>
      <button
        className="secondary"
        disabled={busy || value.page * value.page_size >= value.total}
        onClick={() => change(value.page + 1)}
      >
        Sau →
      </button>
    </div>
  );
}
function Issues({ warnings = [], conflicts = [] }) {
  return (
    <div className="schedule-issues">
      {conflicts.map((item, i) => (
        <p key={"c" + i} className="error">
          {item.message}
        </p>
      ))}
      {warnings.map((item, i) => (
        <p key={"w" + i} className="warning">
          {item.message}
        </p>
      ))}
    </div>
  );
}
function Revision({ value, rooms, departments }) {
  if (!value) return null;
  return (
    <div className="revision-detail">
      <span className="tag">
        {value.kind === "MEETING" ? "Họp" : "Công tác"}
      </span>
      <h3>{value.title}</h3>
      <p className="schedule-period">
        {stamp(value.starts_at)} → {stamp(value.ends_at)}
      </p>
      <p>
        {value.kind === "MEETING"
          ? rooms.find((r) => r.id === value.room_id)?.name || "Phòng họp"
          : value.work_location}
      </p>
      {value.kind === "WORK" && (
        <p className="muted">
          {departments.find((d) => d.id === value.department_id)?.name} ·{" "}
          {value.work_context === "EXTERNAL" ? "Ngoài đơn vị" : "Trong đơn vị"}
        </p>
      )}
      <div className="schedule-description">
        {value.description || "Không có mô tả bổ sung."}
      </div>
      <h4>Thành phần</h4>
      <ul className="participant-detail">
        {value.participants.map((p) => (
          <li key={p.user.id}>
            <span>
              {p.user.full_name} <small>· {p.user.employee_code}</small>
            </span>
            <span className="tag">
              {value.chair_user_id === p.user.id
                ? "Chủ trì · Bắt buộc"
                : p.is_required
                  ? "Bắt buộc"
                  : "Tùy chọn"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Scheduling({
  mode,
  api,
  user,
  rooms,
  departments,
  directory,
  loading,
}) {
  const [draft, setDraft] = useState(() => initialDraft(user));
  const [checked, setChecked] = useState(null),
    [ack, setAck] = useState(false),
    [newParticipant, setNewParticipant] = useState("");
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [list, setList] = useState(null),
    [page, setPage] = useState(1),
    [filterStatus, setFilterStatus] = useState("PENDING"),
    [relation, setRelation] = useState("MINE");
  const [proposal, setProposal] = useState(null),
    [schedule, setSchedule] = useState(null),
    [audit, setAudit] = useState([]),
    [reason, setReason] = useState("");
  const [editing, setEditing] = useState(null),
    [cancelDraft, setCancelDraft] = useState(null);
  const [versions, setVersions] = useState([]),
    [viewedRevision, setViewedRevision] = useState(null);
  // Kept in memory while navigating tabs. A retry keeps the original key and body.
  const [intent, setIntent] = useState(null),
    [warning, setWarning] = useState(null),
    [confirmWarning, setConfirmWarning] = useState(false),
    [uncertain, setUncertain] = useState(false);
  const active = modes.includes(mode);
  const eligiblePeople =
    draft.kind === "WORK"
      ? directory.filter(
          (p) =>
            p.department_id ===
            (editing?.current_revision.department_id || user.department_id),
        )
      : directory;
  const names = new Map(
    [
      ...(editing?.current_revision.participants.map((p) => p.user) || []),
      ...directory,
    ].map((p) => [p.id, p.full_name + " · " + p.employee_code]),
  );
  async function fetchList(pageNo = page) {
    if (mode === "new_schedule" || !active) return;
    const params = new URLSearchParams({ page: pageNo, page_size: 20 });
    const path = mode === "my_schedules" ? "/schedules" : "/proposals";
    if (mode === "my_schedules") params.set("relation", "RELATED");
    else {
      params.set("scope", mode === "review" ? "REVIEWABLE" : relation);
      if (filterStatus) params.set("status", filterStatus);
    }
    setList(await api(path + "?" + params));
    setPage(pageNo);
  }
  useEffect(() => {
    if (editing && mode !== "my_schedules") {
      setEditing(null);
      setDraft(initialDraft(user));
      setChecked(null);
      setAck(false);
    }
    if (active) {
      setError("");
      setNotice("");
      setList(null);
      setPage(1);
    }
  }, [mode]);
  useEffect(() => {
    let current = true;
    if (active && mode !== "new_schedule") {
      setBusy(true);
      const params = new URLSearchParams({ page, page_size: 20 });
      const path = mode === "my_schedules" ? "/schedules" : "/proposals";
      if (mode === "my_schedules") params.set("relation", "RELATED");
      else {
        params.set("scope", mode === "review" ? "REVIEWABLE" : relation);
        if (filterStatus) params.set("status", filterStatus);
      }
      api(path + "?" + params)
        .then((data) => current && setList(data))
        .catch((e) => current && setError(e.message))
        .finally(() => current && setBusy(false));
    }
    return () => {
      current = false;
    };
  }, [mode, page, filterStatus, relation]);

  function update(patch) {
    setDraft((d) => ({ ...d, ...patch }));
    setChecked(null);
    setAck(false);
    setError("");
    setNotice("");
  }
  function candidate() {
    const common = {
      kind: draft.kind,
      title: draft.title,
      description: draft.description,
      starts_at: new Date(draft.start).toISOString(),
      ends_at: new Date(draft.end).toISOString(),
    };
    if (draft.kind === "MEETING")
      return {
        ...common,
        room_id: draft.room_id,
        chair_user_id: draft.chair_user_id,
        participants: draft.participants,
      };
    return {
      ...common,
      department_id:
        editing?.current_revision.department_id || user.department_id,
      work_location: draft.work_location,
      work_context: draft.work_context,
      participant_user_ids: draft.participants.map((p) => p.user_id),
    };
  }
  async function preflight(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    setChecked(null);
    setAck(false);
    try {
      const value = candidate();
      setChecked({
        candidate: value,
        result: await api("/availability/check", "POST", {
          candidate: value,
          ...(editing ? { exclude_schedule_id: editing.id } : {}),
        }),
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function openProposal(id) {
    setProposal(await api("/proposals/" + id));
    setSchedule(null);
    setReason("");
    setError("");
  }
  async function openSchedule(id) {
    setBusy(true);
    setError("");
    try {
      let value = null;
      let rootError = null;
      try {
        value = await api("/schedules/" + id);
      } catch (e) {
        if (e.status !== 404) throw e;
        rootError = e;
      }
      let historyVersions = [];
      try {
        historyVersions = await allPages(
          api,
          "/schedules/" + id + "/revisions",
        );
      } catch (e) {
        if (e.status !== 404) throw e;
      }
      if (!value && !historyVersions.length) throw rootError;
      if (!value) value = { visibility: "HISTORY_ONLY" };
      const history = historyVersions.length
        ? await allPages(api, "/schedules/" + id + "/audit")
        : [];
      setVersions(historyVersions);
      setViewedRevision(
        value.visibility === "HISTORY_ONLY" ? historyVersions[0] : null,
      );
      setAudit(history);
      setSchedule(value);
      setProposal(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function beginEdit(value) {
    const r = value.current_revision;
    setEditing(value);
    setSchedule(null);
    setChecked(null);
    setAck(false);
    setError("");
    setNotice("");
    setNewParticipant("");
    setDraft({
      kind: r.kind,
      title: r.title,
      description: r.description,
      start: localInput(r.starts_at),
      end: localInput(r.ends_at),
      room_id: r.room_id || "",
      chair_user_id: r.chair_user_id || user.id,
      participants: r.participants.map((p) => ({
        user_id: p.user.id,
        is_required: p.is_required,
      })),
      work_location: r.work_location || "",
      work_context: r.work_context || "EXTERNAL",
    });
  }
  async function leaveEdit() {
    const id = editing.id;
    setEditing(null);
    setDraft(initialDraft(user));
    setChecked(null);
    setAck(false);
    setError("");
    await openSchedule(id);
  }
  function requestCancellation(e) {
    e.preventDefault();
    const value = cancelDraft;
    command(
      "/schedules/" +
        value.schedule.id +
        (value.work
          ? "/work-cancellation-proposals"
          : "/meeting-cancellations"),
      {
        expected_schedule_version: value.schedule.row_version,
        reason: value.reason.trim(),
      },
      value.work
        ? "Đã gửi đề nghị hủy. Lịch công tác vẫn có hiệu lực trong lúc chờ."
        : "Đã hủy lịch họp và giải phóng phòng/người.",
    );
  }
  async function attempt(value) {
    setBusy(true);
    setError("");
    setNotice("");
    setUncertain(false);
    let receipt;
    try {
      receipt = await api(value.path, "POST", value.body, { key: value.key });
      if (!receipt?.committed || !receipt?.schedule_id)
        throw new Error("Chưa nhận được biên nhận hợp lệ.");
    } catch (e) {
      if (e.code === "WARNINGS_REQUIRE_ACK") {
        setWarning(e.info);
        setConfirmWarning(false);
      } else if (!e.status || e.status >= 500 || e.status === 408) {
        setUncertain(true);
        setError(
          "Chưa xác nhận được kết quả với máy chủ. Dùng “Thử lại cùng thao tác” để kiểm tra; không tạo lại yêu cầu.",
        );
      } else {
        setError(e.message);
        setIntent(null);
        setWarning(null);
      }
      setBusy(false);
      return;
    }
    setIntent(null);
    setWarning(null);
    setUncertain(false);
    setChecked(null);
    setAck(false);
    setNotice(value.message);
    if (value.creating || value.amending) setDraft(initialDraft(user));
    if (value.amending) setEditing(null);
    setCancelDraft(null);
    try {
      if (receipt.proposal_id) await openProposal(receipt.proposal_id);
      else await openSchedule(receipt.schedule_id);
      await fetchList();
    } catch {
      setError(
        "Thao tác đã lưu thành công. Chưa tải được hồ sơ mới; hãy bấm Tải lại.",
      );
    }
    setBusy(false);
  }
  function command(path, body, message, creating = false, options = {}) {
    if (intent) return;
    const value = {
      path,
      body,
      message,
      creating,
      key: commandKey(),
      ...options,
    };
    setIntent(value);
    attempt(value);
  }
  function submit() {
    if (
      !checked ||
      !checked.result.bookable ||
      (checked.result.warnings.length && !ack)
    )
      return;
    command(
      editing
        ? "/schedules/" + editing.id + "/change-proposals"
        : draft.kind === "MEETING"
          ? "/meeting-proposals"
          : "/work-proposals",
      {
        candidate: checked.candidate,
        warning_acknowledgement_token: ack
          ? checked.result.warning_acknowledgement_token
          : null,
        ...(editing
          ? {
              expected_schedule_version: editing.row_version,
              base_revision_id: editing.current_revision.id,
            }
          : {}),
      },
      editing
        ? "Đã gửi đề nghị sửa. Lịch gốc vẫn giữ nguyên trong lúc chờ."
        : "Đã gửi yêu cầu chờ duyệt. Lịch chưa được xác nhận và chưa giữ chỗ.",
      !editing,
      { amending: !!editing },
    );
  }

  function resolve(action) {
    if (!proposal) return;
    if (action === "REJECT" && !reason.trim()) {
      setError("Vui lòng nhập lý do từ chối.");
      return;
    }
    const body = {
      expected_schedule_version: proposal.schedule_version,
      expected_proposal_version: proposal.row_version,
    };
    if (action === "WITHDRAW") {
      command(
        "/proposals/" + proposal.id + "/withdrawals",
        { ...body, reason: reason.trim() || null },
        "Đã rút yêu cầu.",
      );
    } else
      command(
        "/proposals/" + proposal.id + "/decisions",
        {
          ...body,
          decision: action,
          reason: action === "REJECT" ? reason.trim() : null,
        },
        action === "APPROVE"
          ? proposal.kind === "CANCEL"
            ? "Đã chấp thuận hủy công tác."
            : proposal.kind === "CHANGE"
              ? "Đã duyệt bản sửa và thay thế lịch gốc."
              : "Đã duyệt và xác nhận lịch."
          : "Đã từ chối yêu cầu.",
      );
  }
  const blocked = busy || !!intent || loading;
  if (!active) return null;
  return (
    <div className="scheduling-panel">
      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="notice">
          {notice}
        </div>
      )}
      {uncertain && (
        <div className="info-line">
          Giữ nguyên ý định thao tác cho đến khi biết kết quả.{" "}
          <button
            className="compact"
            disabled={busy}
            onClick={() => attempt(intent)}
          >
            Thử lại cùng thao tác
          </button>
        </div>
      )}
      {mode === "new_schedule" || editing ? (
        <>
          <div className="info-line">
            {editing
              ? "Đề nghị sửa lịch: lịch gốc tiếp tục có hiệu lực và giữ chỗ trong lúc chờ. Chỉ khi bản sửa được duyệt mới thay thế lịch cũ."
              : "Đăng ký tạo yêu cầu chờ duyệt. Chỉ sau khi được duyệt, phòng và người tham gia mới có lịch bận. Người gửi không được tự duyệt."}
          </div>
          {editing && (
            <div className="heading">
              <h2>Đề nghị sửa lịch</h2>
              <button
                className="secondary compact"
                disabled={blocked}
                onClick={leaveEdit}
              >
                Quay lại hồ sơ
              </button>
            </div>
          )}
          <form className="schedule-form" onSubmit={preflight}>
            <fieldset disabled={blocked} className="plain-fieldset">
              <div className="form-grid">
                <label>
                  Loại lịch
                  <select
                    value={draft.kind}
                    disabled={!!editing}
                    onChange={(e) => {
                      setNewParticipant("");
                      update({
                        kind: e.target.value,
                        participants: [{ user_id: user.id, is_required: true }],
                        chair_user_id: user.id,
                      });
                    }}
                  >
                    <option value="MEETING">Họp tại phòng nội bộ</option>
                    <option value="WORK">Công tác cá nhân / nhóm</option>
                  </select>
                </label>
                <label>
                  Tiêu đề
                  <input
                    required
                    maxLength={255}
                    value={draft.title}
                    onChange={(e) => update({ title: e.target.value })}
                  />
                </label>
                <label>
                  Bắt đầu (giờ máy của bạn)
                  <input
                    required
                    type="datetime-local"
                    value={draft.start}
                    onChange={(e) => update({ start: e.target.value })}
                  />
                </label>
                <label>
                  Kết thúc (bao gồm di chuyển nếu công tác)
                  <input
                    required
                    type="datetime-local"
                    value={draft.end}
                    onChange={(e) => update({ end: e.target.value })}
                  />
                </label>
                {draft.kind === "MEETING" ? (
                  <>
                    <label>
                      Phòng họp
                      <select
                        required
                        value={draft.room_id}
                        onChange={(e) => update({ room_id: e.target.value })}
                      >
                        <option value="">Chọn phòng</option>
                        {rooms
                          .filter((r) => r.accepts_new_requests)
                          .map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.code} · {r.name} ·{" "}
                              {r.effective_policy?.capacity || "?"} người
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Chủ trì
                      <select
                        required
                        value={draft.chair_user_id}
                        onChange={(e) =>
                          update({
                            chair_user_id: e.target.value,
                            participants: draft.participants.map((p) =>
                              p.user_id === e.target.value
                                ? { ...p, is_required: true }
                                : p,
                            ),
                          })
                        }
                      >
                        {draft.participants.map((p) => (
                          <option key={p.user_id} value={p.user_id}>
                            {names.get(p.user_id) || "Người tham gia"}
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                ) : (
                  <>
                    <label>
                      Địa điểm công tác
                      <input
                        required
                        maxLength={500}
                        value={draft.work_location}
                        onChange={(e) =>
                          update({ work_location: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      Phạm vi
                      <select
                        value={draft.work_context}
                        onChange={(e) =>
                          update({ work_context: e.target.value })
                        }
                      >
                        <option value="EXTERNAL">Ngoài đơn vị</option>
                        <option value="INTERNAL">Trong đơn vị</option>
                      </select>
                    </label>
                  </>
                )}
              </div>
              <label>
                Nội dung / mục đích
                <textarea
                  maxLength={10000}
                  rows={4}
                  value={draft.description}
                  onChange={(e) => update({ description: e.target.value })}
                />
              </label>
              <fieldset>
                <legend>
                  {draft.kind === "MEETING"
                    ? "Thành phần dự họp"
                    : "Người đi công tác cùng phòng ban"}
                </legend>
                <div className="add-participant">
                  <select
                    aria-label="Thêm người tham gia"
                    value={newParticipant}
                    onChange={(e) => setNewParticipant(e.target.value)}
                  >
                    <option value="">Chọn người tham gia</option>
                    {eligiblePeople
                      .filter(
                        (p) =>
                          !draft.participants.some((x) => x.user_id === p.id),
                      )
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.full_name} · {p.employee_code}
                        </option>
                      ))}
                  </select>
                  <button
                    type="button"
                    className="secondary compact"
                    disabled={!newParticipant}
                    onClick={() => {
                      update({
                        participants: [
                          ...draft.participants,
                          { user_id: newParticipant, is_required: true },
                        ],
                      });
                      setNewParticipant("");
                    }}
                  >
                    Thêm
                  </button>
                </div>
                <div className="participant-editor">
                  {draft.participants.map((p) => (
                    <div className="participant-row" key={p.user_id}>
                      <span>{names.get(p.user_id) || user.full_name}</span>
                      {draft.kind === "MEETING" ? (
                        <label className="check">
                          <input
                            type="checkbox"
                            checked={p.is_required}
                            disabled={p.user_id === draft.chair_user_id}
                            onChange={(e) =>
                              update({
                                participants: draft.participants.map((x) =>
                                  x.user_id === p.user_id
                                    ? { ...x, is_required: e.target.checked }
                                    : x,
                                ),
                              })
                            }
                          />
                          Bắt buộc
                        </label>
                      ) : (
                        <span className="tag">Bắt buộc</span>
                      )}
                      <button
                        type="button"
                        className="text-button danger"
                        disabled={
                          draft.participants.length === 1 ||
                          (draft.kind === "MEETING" &&
                            p.user_id === draft.chair_user_id)
                        }
                        onClick={() =>
                          update({
                            participants: draft.participants.filter(
                              (x) => x.user_id !== p.user_id,
                            ),
                          })
                        }
                      >
                        Bỏ
                      </button>
                    </div>
                  ))}
                </div>
              </fieldset>
              <p className="muted">
                {draft.kind === "MEETING"
                  ? "Họp dài 15 phút–4 giờ, gửi trước ít nhất 30 phút và trong 90 ngày tới. Tính cả người tùy chọn khi kiểm tra sức chứa."
                  : "Công tác dùng toàn khoảng liên tục, mọi người đều bắt buộc và cùng phòng ban. Thời gian nhập phải gồm cả di chuyển."}
              </p>
              <button className="compact" type="submit">
                Kiểm tra phương án
              </button>
            </fieldset>
          </form>
          {checked && (
            <div className="preflight-result">
              <h3>
                {checked.result.bookable
                  ? "Phương án có thể gửi để xét duyệt"
                  : "Cần điều chỉnh phương án"}
              </h3>
              <p className="muted">
                Đã kiểm tra lúc {stamp(checked.result.checked_at)}. Kết quả này
                chưa giữ tài nguyên.
              </p>
              <Issues {...checked.result} />
              {!!checked.result.warnings.length && (
                <label className="check">
                  <input
                    type="checkbox"
                    checked={ack}
                    onChange={(e) => setAck(e.target.checked)}
                    disabled={blocked}
                  />
                  Tôi đã đọc và đồng ý tiếp tục với các cảnh báo trên.
                </label>
              )}
              <button
                className="compact"
                disabled={
                  blocked ||
                  !checked.result.bookable ||
                  (!!checked.result.warnings.length && !ack)
                }
                onClick={submit}
              >
                {editing ? "Gửi đề nghị sửa lịch" : "Gửi yêu cầu chờ duyệt"}
              </button>
            </div>
          )}
        </>
      ) : (
        <>
          <div className="list-toolbar">
            {mode !== "my_schedules" && (
              <>
                <select
                  aria-label="Lọc trạng thái yêu cầu"
                  value={filterStatus}
                  onChange={(e) => {
                    setFilterStatus(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">Tất cả trạng thái</option>
                  {Object.entries(statusNames).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
                {mode === "my_proposals" && (
                  <select
                    aria-label="Phạm vi yêu cầu"
                    value={relation}
                    onChange={(e) => {
                      setRelation(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="MINE">Do tôi gửi</option>
                    <option value="RELATED">Tôi được xem</option>
                  </select>
                )}
              </>
            )}
            <span>{list?.total || 0} hồ sơ</span>
            <button
              className="secondary compact"
              disabled={busy}
              onClick={() => {
                setError("");
                setBusy(true);
                fetchList()
                  .catch((e) => setError(e.message))
                  .finally(() => setBusy(false));
              }}
            >
              Tải lại
            </button>
          </div>
          {mode === "review" && (
            <p className="info-line">
              Chỉ hiển thị yêu cầu thuộc phạm vi được phân công và khác người
              gửi. Duyệt sẽ kiểm tra lại phòng, thành phần và quyền hiện tại.
            </p>
          )}
          {busy && !list ? (
            <p role="status">Đang tải hồ sơ…</p>
          ) : !list?.items.length ? (
            <div className="empty">
              <span>▦</span>
              <p>Không có hồ sơ phù hợp trong phạm vi của bạn.</p>
            </div>
          ) : (
            <div className="proposal-list">
              {list.items.map((item) => (
                <article className="proposal-card" key={item.id}>
                  <div>
                    <span
                      className={
                        "tag state-" +
                        (item.status || item.lifecycle).toLowerCase()
                      }
                    >
                      {statusNames[item.status] ||
                        lifecycleNames[item.lifecycle]}
                    </span>
                    <span className="tag">
                      {(item.schedule_kind || item.kind) === "MEETING"
                        ? "Họp"
                        : "Công tác"}
                    </span>
                    {item.status && (
                      <span className="tag">
                        {
                          {
                            CREATE: "Tạo lịch",
                            CHANGE: "Đề nghị sửa",
                            CANCEL: "Đề nghị hủy",
                          }[item.kind]
                        }
                      </span>
                    )}
                    <h3>{item.title}</h3>
                    <p className="muted">
                      {mode === "my_schedules"
                        ? `${stamp(item.starts_at)} → ${stamp(item.ends_at)}`
                        : `Gửi ${stamp(item.created_at)} · Hạn xử lý ${stamp(item.expires_at)}`}
                    </p>
                  </div>
                  <button
                    className="secondary compact"
                    disabled={busy}
                    onClick={() =>
                      mode === "my_schedules"
                        ? openSchedule(item.id)
                        : (setBusy(true),
                          openProposal(item.id)
                            .catch((e) => setError(e.message))
                            .finally(() => setBusy(false)))
                    }
                  >
                    Xem chi tiết
                  </button>
                </article>
              ))}
            </div>
          )}
          <Pager value={list} busy={busy} change={setPage} />
        </>
      )}
      {proposal && !warning && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="proposal-title"
          >
            <div className="modal-heading">
              <h2 id="proposal-title">Chi tiết yêu cầu</h2>
              <button
                className="text-button"
                disabled={!!intent || busy}
                onClick={() => {
                  setProposal(null);
                  setError("");
                }}
              >
                Đóng ×
              </button>
            </div>
            {error && (
              <div role="alert" className="error">
                {error}
              </div>
            )}
            {uncertain && (
              <button
                className="compact"
                disabled={busy}
                onClick={() => attempt(intent)}
              >
                Thử lại cùng thao tác
              </button>
            )}
            <span className={"tag state-" + proposal.status.toLowerCase()}>
              {statusNames[proposal.status]}
            </span>
            <p className="muted">
              Người gửi: {proposal.submitted_by.full_name} · Hạn xử lý:{" "}
              {stamp(proposal.expires_at)}
            </p>
            <span className="tag">
              {
                {
                  CREATE: "Tạo lịch",
                  CHANGE: "Đề nghị sửa",
                  CANCEL: "Đề nghị hủy công tác",
                }[proposal.kind]
              }
            </span>
            {proposal.kind === "CANCEL" && <h3>{proposal.title}</h3>}
            <Revision
              value={proposal.candidate}
              rooms={rooms}
              departments={departments}
            />
            {proposal.base_comparison && (
              <div className="base-comparison">
                <h4>
                  {proposal.kind === "CANCEL"
                    ? "Lịch công tác đề nghị hủy"
                    : "So sánh với lịch gốc"}
                </h4>
                <p>
                  {stamp(proposal.base_comparison.starts_at)} →{" "}
                  {stamp(proposal.base_comparison.ends_at)}
                </p>
                {proposal.base_comparison.room_id && (
                  <p>
                    Phòng gốc:{" "}
                    {rooms.find(
                      (r) => r.id === proposal.base_comparison.room_id,
                    )?.name || "Phòng họp"}
                  </p>
                )}
                {proposal.kind === "CHANGE" && (
                  <p className="muted">
                    Nội dung thay đổi:{" "}
                    {proposal.base_comparison.changed_fields
                      .map(
                        (k) =>
                          ({
                            title: "Tiêu đề",
                            description: "Nội dung",
                            starts_at: "Bắt đầu",
                            ends_at: "Kết thúc",
                            room_id: "Phòng họp",
                            chair_user_id: "Chủ trì",
                            participants: "Thành phần",
                            department_id: "Phòng ban",
                            work_location: "Địa điểm",
                            work_context: "Phạm vi",
                          })[k],
                      )
                      .join(", ") || "Không thay đổi trường hiển thị"}
                  </p>
                )}
              </div>
            )}
            {proposal.reason && (
              <p className="info-line">Lý do: {proposal.reason}</p>
            )}
            {proposal.resolved_by && (
              <p className="muted">
                Xử lý bởi {proposal.resolved_by.full_name} ·{" "}
                {stamp(proposal.resolved_at)}
              </p>
            )}
            {proposal.email_summary && (
              <p className="info-line">
                Thông báo: {proposal.email_summary.pending} chờ gửi,{" "}
                {proposal.email_summary.smtp_accepted} được máy chủ SMTP tiếp
                nhận. Gửi email thật sẽ được triển khai ở mốc sau.
              </p>
            )}
            {proposal.status === "PENDING" && (
              <p className="muted">
                {proposal.kind === "CREATE"
                  ? "Yêu cầu đang chờ chưa giữ phòng/người. Nếu phát sinh xung đột, thao tác duyệt có thể bị chặn."
                  : proposal.kind === "CHANGE"
                    ? "Lịch gốc vẫn đang có hiệu lực. Phương án sửa chưa giữ chỗ mới và sẽ được kiểm tra lại lúc duyệt."
                    : "Lịch công tác gốc vẫn có hiệu lực. Chỉ giải phóng lịch bận sau khi đề nghị hủy được chấp thuận."}
              </p>
            )}
            {proposal.allowed_actions.length > 0 && (
              <>
                <label>
                  Lý do (bắt buộc khi từ chối)
                  <textarea
                    rows={3}
                    maxLength={1000}
                    value={reason}
                    disabled={blocked}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <div className="modal-footer">
                  <button
                    className="secondary compact"
                    disabled={blocked}
                    onClick={() => {
                      setBusy(true);
                      openProposal(proposal.id)
                        .catch((e) => setError(e.message))
                        .finally(() => setBusy(false));
                    }}
                  >
                    Tải trạng thái mới
                  </button>
                  {proposal.allowed_actions.includes("WITHDRAW") && (
                    <button
                      className="compact"
                      disabled={blocked}
                      onClick={() => resolve("WITHDRAW")}
                    >
                      Rút yêu cầu
                    </button>
                  )}
                  {proposal.allowed_actions.includes("REJECT") && (
                    <button
                      className="secondary compact"
                      disabled={blocked}
                      onClick={() => resolve("REJECT")}
                    >
                      Từ chối
                    </button>
                  )}
                  {proposal.allowed_actions.includes("APPROVE") && (
                    <button
                      className="compact"
                      disabled={blocked}
                      onClick={() => resolve("APPROVE")}
                    >
                      {proposal.kind === "CANCEL"
                        ? "Chấp thuận hủy công tác"
                        : proposal.kind === "CHANGE"
                          ? "Duyệt bản sửa lịch"
                          : "Duyệt và xác nhận lịch"}
                    </button>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      )}
      {warning && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="warning-title"
          >
            <h2 id="warning-title">Cần xác nhận cảnh báo hiện tại</h2>
            {error && (
              <div className="error" role="alert">
                {error}
              </div>
            )}
            {uncertain && (
              <button
                className="compact"
                disabled={busy}
                onClick={() => attempt(intent)}
              >
                Thử lại cùng thao tác
              </button>
            )}
            <p>
              Thông tin đã thay đổi hoặc phương án có cảnh báo cần bạn xem lại
              trước khi tiếp tục.
            </p>
            <Issues warnings={warning.warnings} />
            <label className="check">
              <input
                type="checkbox"
                checked={confirmWarning}
                disabled={busy}
                onChange={(e) => setConfirmWarning(e.target.checked)}
              />
              Tôi đã đọc và đồng ý tiếp tục.
            </label>
            <div className="modal-footer">
              <button
                className="secondary compact"
                disabled={busy}
                onClick={() => {
                  setIntent(null);
                  setWarning(null);
                  setError("");
                }}
              >
                Quay lại kiểm tra
              </button>
              <button
                className="compact"
                disabled={busy || !confirmWarning}
                onClick={() => {
                  const value = {
                    ...intent,
                    body: {
                      ...intent.body,
                      warning_acknowledgement_token:
                        warning.warning_acknowledgement_token,
                    },
                  };
                  setIntent(value);
                  attempt(value);
                }}
              >
                Xác nhận và tiếp tục
              </button>
            </div>
          </section>
        </div>
      )}
      {schedule && !cancelDraft && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="schedule-title"
          >
            <div className="modal-heading">
              <h2 id="schedule-title">Hồ sơ lịch</h2>
              <button
                className="text-button"
                disabled={blocked}
                onClick={() => {
                  setSchedule(null);
                  setViewedRevision(null);
                  setError("");
                }}
              >
                Đóng ×
              </button>
            </div>
            {error && (
              <div className="error" role="alert">
                {error}
              </div>
            )}
            {schedule.visibility === "BUSY_ONLY" ? (
              <p>
                Đã có lịch: {stamp(schedule.starts_at)} →{" "}
                {stamp(schedule.ends_at)}
              </p>
            ) : schedule.visibility === "HISTORY_ONLY" ? (
              <p className="info-line">
                Bạn chỉ được xem các phiên bản lịch sử trong phạm vi của mình
                bên dưới.
              </p>
            ) : (
              <>
                <span className="tag">
                  {lifecycleNames[schedule.lifecycle]}
                </span>
                <Revision
                  value={schedule.current_revision}
                  rooms={rooms}
                  departments={departments}
                />
                {!schedule.current_revision && (
                  <p className="info-line">
                    Lịch chưa có phiên bản được xác nhận. Xem yêu cầu tại mục
                    Yêu cầu của tôi.
                  </p>
                )}
                {schedule.cancellation && (
                  <div className="info-line">
                    Đã hủy bởi {schedule.cancellation.cancelled_by.full_name}{" "}
                    lúc {stamp(schedule.cancellation.cancelled_at)}. Lý do:{" "}
                    {schedule.cancellation.reason}
                  </div>
                )}
                {schedule.allowed_actions.length > 0 && (
                  <div className="modal-footer">
                    {schedule.allowed_actions.includes("REQUEST_CHANGE") && (
                      <button
                        className="secondary compact"
                        disabled={blocked}
                        onClick={() => beginEdit(schedule)}
                      >
                        Đề nghị sửa lịch
                      </button>
                    )}
                    {schedule.allowed_actions.includes("CANCEL_MEETING") && (
                      <button
                        className="compact"
                        disabled={blocked}
                        onClick={() => {
                          setCancelDraft({ schedule, work: false, reason: "" });
                          setError("");
                        }}
                      >
                        Hủy lịch họp
                      </button>
                    )}
                    {schedule.allowed_actions.includes(
                      "REQUEST_WORK_CANCELLATION",
                    ) && (
                      <button
                        className="compact"
                        disabled={blocked}
                        onClick={() => {
                          setCancelDraft({ schedule, work: true, reason: "" });
                          setError("");
                        }}
                      >
                        Đề nghị hủy công tác
                      </button>
                    )}
                  </div>
                )}
              </>
            )}
            {!!versions.length && (
              <>
                <h4>Các phiên bản được phép xem</h4>
                <div className="version-buttons">
                  {versions.map((r) => (
                    <button
                      className="secondary compact"
                      key={r.id}
                      disabled={busy}
                      onClick={() => setViewedRevision(r)}
                    >
                      Phiên bản {r.revision_no} · {stamp(r.starts_at)}
                    </button>
                  ))}
                </div>
                {viewedRevision && (
                  <div className="historical-revision">
                    <p className="info-line">
                      Đang xem bản lịch sử số {viewedRevision.revision_no}.
                      Quyền sửa/hủy chỉ áp dụng trên lịch đang có hiệu lực.
                    </p>
                    <Revision
                      value={viewedRevision}
                      rooms={rooms}
                      departments={departments}
                    />
                  </div>
                )}
                <h4>Lịch sử xử lý</h4>
                <ul className="audit-list">
                  {audit.map((a) => (
                    <li key={a.id}>
                      <b>{a.summary}</b>
                      <small>
                        {a.actor?.full_name || "Hệ thống"} ·{" "}
                        {stamp(a.occurred_at)}
                      </small>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {schedule.visibility === "DETAIL" && (
              <button
                className="secondary compact"
                disabled={blocked}
                onClick={() => openSchedule(schedule.id)}
              >
                Tải lại hồ sơ lịch
              </button>
            )}
          </section>
        </div>
      )}
      {cancelDraft && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cancel-title"
          >
            <h2 id="cancel-title">
              {cancelDraft.work
                ? "Đề nghị hủy công tác"
                : "Xác nhận hủy lịch họp"}
            </h2>
            {error && (
              <div className="error" role="alert">
                {error}
              </div>
            )}
            {uncertain && (
              <button
                className="compact"
                disabled={busy}
                onClick={() => attempt(intent)}
              >
                Thử lại cùng thao tác
              </button>
            )}
            <p>
              <b>{cancelDraft.schedule.current_revision.title}</b>
            </p>
            <p>
              {stamp(cancelDraft.schedule.current_revision.starts_at)} →{" "}
              {stamp(cancelDraft.schedule.current_revision.ends_at)}
            </p>
            <div className="info-line">
              {cancelDraft.work
                ? "Lịch công tác vẫn có hiệu lực trong lúc chờ. Người phụ trách phòng ban sẽ xét đề nghị hủy."
                : "Hủy cuộc họp sẽ giải phóng phòng, thời gian chuyển tiếp và lịch bận do cuộc họp này tạo ra. Đề nghị sửa đang chờ (nếu có) sẽ hết hiệu lực."}
            </div>
            <form onSubmit={requestCancellation}>
              <label>
                Lý do hủy
                <textarea
                  required
                  maxLength={1000}
                  rows={4}
                  disabled={blocked}
                  value={cancelDraft.reason}
                  onChange={(e) =>
                    setCancelDraft({ ...cancelDraft, reason: e.target.value })
                  }
                />
              </label>
              <div className="modal-footer">
                <button
                  className="secondary compact"
                  type="button"
                  disabled={blocked}
                  onClick={async () => {
                    const id = cancelDraft.schedule.id;
                    setCancelDraft(null);
                    setError("");
                    await openSchedule(id);
                  }}
                >
                  Quay lại hồ sơ
                </button>
                <button
                  className="compact"
                  type="submit"
                  disabled={blocked || !cancelDraft.reason.trim()}
                >
                  {cancelDraft.work
                    ? "Gửi đề nghị hủy công tác"
                    : "Xác nhận hủy lịch họp"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
