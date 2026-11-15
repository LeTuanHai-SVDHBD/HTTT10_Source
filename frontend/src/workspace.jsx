import React, { useEffect, useState } from "react";
import { allPages, roles, localInput, stamp } from "./api";
import Scheduling from "./scheduling";
import UsageReport from "./reports";
import { Dialog, Icon, useSmallScreen } from "./ui";

const tabs = {
  calendar: "Lịch công tác",
  finder: "Tìm phòng trống",
  new_schedule: "Tạo yêu cầu lịch",
  my_proposals: "Yêu cầu của tôi",
  review: "Chờ tôi duyệt",
  my_schedules: "Hồ sơ lịch",
  rooms: "Phòng họp",
  departments: "Phòng ban",
  users: "Tài khoản",
  reports: "Báo cáo phòng",
};
const weekdays = [
  "Thứ Hai",
  "Thứ Ba",
  "Thứ Tư",
  "Thứ Năm",
  "Thứ Sáu",
  "Thứ Bảy",
  "Chủ nhật",
];
const defaultWindows = () =>
  [1, 2, 3, 4, 5].flatMap((weekday) => [
    { weekday, start_time: "08:00", end_time: "12:00" },
    { weekday, start_time: "13:00", end_time: "17:00" },
  ]);
const newPolicy = () => ({
  effective_from: localInput(Date.now() + 120000),
  capacity: 10,
  buffer_minutes: 15,
  weekly_windows: defaultWindows(),
  calendar_days: [],
});
const cleanPolicy = (p) => ({
  effective_from: localInput(p.effective_from),
  capacity: p.capacity,
  buffer_minutes: p.buffer_minutes,
  weekly_windows: p.weekly_windows,
  calendar_days: p.calendar_days,
});
const encodePolicy = (p) => ({
  ...p,
  effective_from: new Date(p.effective_from).toISOString(),
});

function Pager({ value, change }) {
  if (!value || value.total <= value.page_size) return null;
  return (
    <div className="pager">
      <button
        className="secondary"
        disabled={value.page === 1}
        onClick={() => change(value.page - 1)}
      >
        ← Trước
      </button>
      <span>
        Trang {value.page} / {Math.ceil(value.total / value.page_size)}
      </span>
      <button
        className="secondary"
        disabled={value.page * value.page_size >= value.total}
        onClick={() => change(value.page + 1)}
      >
        Sau →
      </button>
    </div>
  );
}
function PolicyFields({ value, onChange }) {
  const update = (patch) => onChange({ ...value, ...patch });
  const setWindow = (i, patch) =>
    update({
      weekly_windows: value.weekly_windows.map((w, n) =>
        n === i ? { ...w, ...patch } : w,
      ),
    });
  const setDay = (i, patch) =>
    update({
      calendar_days: value.calendar_days.map((d, n) =>
        n === i ? { ...d, ...patch } : d,
      ),
    });
  return (
    <fieldset>
      <legend>Sức chứa & giờ phục vụ</legend>
      <div className="form-grid">
        <label>
          Có hiệu lực từ (giờ máy của bạn)
          <input
            required
            type="datetime-local"
            value={value.effective_from}
            onChange={(e) => update({ effective_from: e.target.value })}
          />
        </label>
        <label>
          Sức chứa
          <input
            required
            type="number"
            min="1"
            max="65535"
            value={value.capacity}
            onChange={(e) => update({ capacity: Number(e.target.value) })}
          />
        </label>
        <label>
          Chuyển tiếp sau họp (phút)
          <input
            required
            type="number"
            min="0"
            max="65535"
            value={value.buffer_minutes}
            onChange={(e) => update({ buffer_minutes: Number(e.target.value) })}
          />
        </label>
      </div>
      <p className="muted">
        Giờ phục vụ được hiểu theo múi giờ Việt Nam. Cuộc họp nằm trọn trong một
        khoảng; phần chuyển tiếp có thể nằm ngoài giờ phục vụ.
      </p>
      <div className="window-list">
        {value.weekly_windows.map((w, i) => (
          <div className="window-row" key={i}>
            <select
              aria-label="Thứ phục vụ"
              value={w.weekday}
              onChange={(e) =>
                setWindow(i, { weekday: Number(e.target.value) })
              }
            >
              {weekdays.map((d, n) => (
                <option key={d} value={n + 1}>
                  {d}
                </option>
              ))}
            </select>
            <input
              aria-label="Giờ mở"
              type="time"
              required
              value={w.start_time}
              onChange={(e) => setWindow(i, { start_time: e.target.value })}
            />
            <span>đến</span>
            <input
              aria-label="Giờ đóng"
              type="time"
              required
              value={w.end_time}
              onChange={(e) => setWindow(i, { end_time: e.target.value })}
            />
            <button
              type="button"
              className="text-button danger"
              onClick={() =>
                update({
                  weekly_windows: value.weekly_windows.filter(
                    (_, n) => n !== i,
                  ),
                })
              }
            >
              Xóa
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="secondary compact"
        onClick={() =>
          update({
            weekly_windows: [
              ...value.weekly_windows,
              { weekday: 1, start_time: "08:00", end_time: "12:00" },
            ],
          })
        }
      >
        + Khoảng phục vụ
      </button>
      <h4>Ngày nghỉ / ngày mở cửa riêng</h4>
      {value.calendar_days.map((d, i) => (
        <div className="exception" key={i}>
          <div className="form-grid">
            <label>
              Ngày
              <input
                type="date"
                required
                value={d.local_date}
                onChange={(e) => setDay(i, { local_date: e.target.value })}
              />
            </label>
            <label>
              Lý do
              <input
                required
                maxLength={255}
                value={d.reason}
                onChange={(e) => setDay(i, { reason: e.target.value })}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={d.is_closed}
                onChange={(e) =>
                  setDay(i, {
                    is_closed: e.target.checked,
                    windows: e.target.checked
                      ? []
                      : [{ start_time: "08:00", end_time: "17:00" }],
                  })
                }
              />
              Nghỉ cả ngày
            </label>
          </div>
          {!d.is_closed && (
            <>
              {d.windows.map((w, j) => (
                <div className="window-row" key={j}>
                  <input
                    aria-label="Giờ mở ngày riêng"
                    type="time"
                    required
                    value={w.start_time}
                    onChange={(e) =>
                      setDay(i, {
                        windows: d.windows.map((x, n) =>
                          n === j ? { ...x, start_time: e.target.value } : x,
                        ),
                      })
                    }
                  />
                  <span>đến</span>
                  <input
                    aria-label="Giờ đóng ngày riêng"
                    type="time"
                    required
                    value={w.end_time}
                    onChange={(e) =>
                      setDay(i, {
                        windows: d.windows.map((x, n) =>
                          n === j ? { ...x, end_time: e.target.value } : x,
                        ),
                      })
                    }
                  />
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      setDay(i, {
                        windows: d.windows.filter((_, n) => n !== j),
                      })
                    }
                  >
                    Xóa khoảng
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="text-button"
                onClick={() =>
                  setDay(i, {
                    windows: [
                      ...d.windows,
                      { start_time: "13:00", end_time: "17:00" },
                    ],
                  })
                }
              >
                + Khoảng mở riêng
              </button>
            </>
          )}
          <button
            type="button"
            className="text-button danger"
            onClick={() =>
              update({
                calendar_days: value.calendar_days.filter((_, n) => n !== i),
              })
            }
          >
            Xóa ngày ngoại lệ
          </button>
        </div>
      ))}
      <button
        type="button"
        className="secondary compact"
        onClick={() =>
          update({
            calendar_days: [
              ...value.calendar_days,
              { local_date: "", is_closed: true, reason: "", windows: [] },
            ],
          })
        }
      >
        + Ngày ngoại lệ
      </button>
    </fieldset>
  );
}
function EquipmentFields({ value, onChange }) {
  const set = (i, patch) =>
    onChange(value.map((r, n) => (n === i ? { ...r, ...patch } : r)));
  return (
    <fieldset>
      <legend>Thiết bị</legend>
      {value.map((e, i) => (
        <div className="form-grid equipment-row" key={i}>
          <label>
            Mã thiết bị
            <input
              required
              maxLength={40}
              value={e.equipment_code}
              onChange={(x) => set(i, { equipment_code: x.target.value })}
            />
          </label>
          <label>
            Tên thiết bị
            <input
              required
              maxLength={120}
              value={e.display_name}
              onChange={(x) => set(i, { display_name: x.target.value })}
            />
          </label>
          <label>
            Số lượng
            <input
              type="number"
              required
              min="1"
              max="65535"
              value={e.quantity}
              onChange={(x) => set(i, { quantity: Number(x.target.value) })}
            />
          </label>
          <button
            type="button"
            className="text-button danger"
            onClick={() => onChange(value.filter((_, n) => n !== i))}
          >
            Xóa
          </button>
        </div>
      ))}
      <button
        type="button"
        className="secondary compact"
        onClick={() =>
          onChange([
            ...value,
            { equipment_code: "", display_name: "", quantity: 1 },
          ])
        }
      >
        + Thiết bị
      </button>
    </fieldset>
  );
}

export default function Workspace({ api, user, logout, changePassword }) {
  const isAdmin = user.roles.includes("ADMIN");
  const smallScreen = useSmallScreen();
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    if (!smallScreen) setMenuOpen(false);
  }, [smallScreen]);
  const [tab, setTab] = useState(() =>
      new URLSearchParams(window.location.search).has("proposal")
        ? "my_proposals"
        : new URLSearchParams(window.location.search).has("schedule")
          ? "my_schedules"
          : "calendar",
    ),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [rooms, setRooms] = useState([]),
    [departments, setDepartments] = useState([]),
    [directory, setDirectory] = useState([]),
    [accounts, setAccounts] = useState([]);
  const [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [editor, setEditor] = useState(null),
    [draft, setDraft] = useState(null);
  const [query, setQuery] = useState(""),
    [accountDept, setAccountDept] = useState(""),
    [accountStatus, setAccountStatus] = useState(""),
    [listPage, setListPage] = useState(1);
  const [calendar, setCalendar] = useState(null),
    [found, setFound] = useState(null),
    [calendarFilter, setCalendarFilter] = useState(null),
    [finderFilter, setFinderFilter] = useState(null);
  const [scope, setScope] = useState(null),
    [history, setHistory] = useState(null);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  async function load() {
    const [r, d, people, a] = await Promise.all([
      allPages(api, "/rooms"),
      allPages(api, "/departments"),
      allPages(api, "/directory/users"),
      isAdmin ? allPages(api, "/users") : Promise.resolve([]),
    ]);
    setRooms(r);
    setDepartments(d);
    setDirectory(people);
    setAccounts(a);
  }
  useEffect(() => {
    let active = true;
    load()
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);
  async function run(action, success) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      if (success) setNotice(success);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function calendarSearch(filter, page = 1) {
    const data = await api(
      "/calendar?" + new URLSearchParams({ ...filter, page, page_size: 20 }),
    );
    setCalendar(data);
    setCalendarFilter(filter);
  }
  async function finderSearch(filter, page = 1) {
    const params = new URLSearchParams({
      starts_at: filter.starts_at,
      ends_at: filter.ends_at,
      participant_count: filter.participant_count,
      page,
      page_size: 12,
    });
    filter.equipment_codes.forEach((e) => params.append("equipment_codes", e));
    setFound(await api("/rooms/availability?" + params));
    setFinderFilter(filter);
  }
  function switchTab(value) {
    setMenuOpen(false);
    setTab(value);
    setError("");
    setNotice("");
    setQuery("");
    setListPage(1);
  }
  function edit(kind, row = null) {
    setError("");
    setNotice("");
    setEditor({ kind, row });
    if (kind === "department")
      setDraft(
        row
          ? {
              code: row.code,
              name: row.name,
              accepts_new_requests: row.accepts_new_requests,
            }
          : { code: "", name: "", accepts_new_requests: true },
      );
    if (kind === "user")
      setDraft(
        row
          ? {
              employee_code: row.employee_code,
              full_name: row.full_name,
              email: row.email,
              department_id: row.department_id,
              status: row.status,
              roles: row.roles,
            }
          : {
              employee_code: "",
              full_name: "",
              email: "",
              department_id:
                departments.find((d) => d.accepts_new_requests)?.id || "",
              status: "ACTIVE",
              roles: ["EMPLOYEE"],
              temporary_password: "",
            },
      );
    if (kind === "room")
      setDraft(
        row
          ? {
              code: row.code,
              name: row.name,
              location: row.location,
              accepts_new_requests: row.accepts_new_requests,
              equipment: row.equipment,
            }
          : {
              code: "",
              name: "",
              location: "",
              accepts_new_requests: true,
              equipment: [],
              initial_policy: {
                ...newPolicy(),
                effective_from: localInput(Date.now() - 60000),
              },
            },
      );
    if (kind === "policy")
      setDraft(
        row.effective_policy
          ? {
              ...cleanPolicy(row.effective_policy),
              effective_from: localInput(Date.now() + 120000),
            }
          : newPolicy(),
      );
    if (kind === "reset") setDraft({ new_temporary_password: "" });
  }
  function patch(values) {
    setDraft((d) => ({ ...d, ...values }));
  }
  async function save(event) {
    event.preventDefault();
    await run(async () => {
      const { kind, row } = editor;
      if (kind === "department")
        await api(
          "/departments" + (row ? "/" + row.id : ""),
          row ? "PUT" : "POST",
          {
            ...draft,
            ...(row ? { expected_department_version: row.row_version } : {}),
          },
        );
      if (kind === "user")
        await api("/users" + (row ? "/" + row.id : ""), row ? "PUT" : "POST", {
          ...draft,
          ...(row ? { expected_user_version: row.row_version } : {}),
        });
      if (kind === "room")
        await api("/rooms" + (row ? "/" + row.id : ""), row ? "PUT" : "POST", {
          ...draft,
          ...(row
            ? { expected_room_version: row.row_version }
            : { initial_policy: encodePolicy(draft.initial_policy) }),
        });
      if (kind === "policy")
        await api("/rooms/" + row.id + "/policies", "POST", {
          ...encodePolicy(draft),
          expected_room_version: row.row_version,
        });
      if (kind === "reset")
        await api("/users/" + row.id + "/temporary-password", "PUT", {
          ...draft,
          expected_user_version: row.row_version,
        });
      setEditor(null);
      setDraft(null);
      await load();
    }, "Đã lưu thay đổi.");
  }
  async function openScope(kind, row) {
    await run(async () => {
      const value = await api(
        `/${kind === "room" ? "rooms" : "departments"}/${row.id}/approvers`,
      );
      setScope({
        kind,
        row,
        value,
        selected: value.approvers.map((u) => u.id),
      });
    });
  }
  async function saveScope(e) {
    e.preventDefault();
    await run(async () => {
      const { kind, row, value, selected } = scope;
      await api(
        `/${kind === "room" ? "rooms" : "departments"}/${row.id}/approvers`,
        "PUT",
        {
          approver_user_ids: selected,
          [kind === "room"
            ? "expected_room_version"
            : "expected_department_version"]:
            value[kind === "room" ? "room_version" : "department_version"],
        },
      );
      setScope(null);
      await load();
    }, "Đã cập nhật người phê duyệt.");
  }
  const equipmentOptions = [
    ...new Map(
      rooms
        .flatMap((r) => r.equipment)
        .map((e) => [e.equipment_code, e.display_name]),
    ).entries(),
  ];
  const text = query.trim().toLocaleLowerCase("vi");
  const list = (
    tab === "rooms" ? rooms : tab === "departments" ? departments : accounts
  )
    .filter((r) =>
      [r.code, r.name, r.location, r.employee_code, r.full_name, r.email]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("vi")
        .includes(text),
    )
    .filter(
      (r) =>
        tab !== "users" ||
        ((!accountDept || r.department_id === accountDept) &&
          (!accountStatus || r.status === accountStatus)),
    );
  const paged = list.slice((listPage - 1) * 12, listPage * 12);
  const closeEditor = () => {
    if (!busy) {
      setEditor(null);
      setDraft(null);
      setError("");
    }
  };
  const navigation = (
    <div className="sidebar-body">
      <div className="sidebar-brand">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="calendar" size={25} />
          </span>
          <b>
            HTTT10<span>Lịch công tác nội bộ</span>
          </b>
        </div>
        {smallScreen && (
          <button
            type="button"
            className="icon-button sidebar-close"
            aria-label="Đóng menu"
            onClick={() => setMenuOpen(false)}
          >
            <Icon name="close" />
          </button>
        )}
      </div>
      <p className="nav-caption">KHÔNG GIAN LÀM VIỆC</p>
      <nav id="main-navigation" aria-label="Điều hướng chính">
        {Object.entries(tabs)
          .filter(
            ([k]) =>
              (isAdmin || k !== "users") &&
              (k !== "new_schedule" || user.roles.includes("EMPLOYEE")) &&
              (k !== "review" || user.roles.includes("APPROVER")) &&
              (k !== "reports" || isAdmin || user.roles.includes("APPROVER")),
          )
          .map(([k, v]) => (
            <button
              key={k}
              className={tab === k ? "nav active" : "nav"}
              aria-current={tab === k ? "page" : undefined}
              onClick={() => switchTab(k)}
            >
              <Icon
                name={
                  {
                    calendar: "calendar",
                    finder: "search",
                    new_schedule: "plus",
                    my_proposals: "inbox",
                    review: "check",
                    my_schedules: "clock",
                    rooms: "building",
                    departments: "layers",
                    users: "users",
                    reports: "chart",
                  }[k]
                }
              />
              <span className="nav-label">{v}</span>
              {tab === k && <span className="nav-dot" aria-hidden="true" />}
            </button>
          ))}
      </nav>
      <div className="sidebar-profile">
        <div className="profile-summary">
          <span className="avatar" aria-hidden="true">
            {user.full_name
              .trim()
              .split(/\s+/)
              .slice(-2)
              .map((n) => n[0])
              .join("")}
          </span>
          <div>
            <b>{user.full_name}</b>
            <small>{user.roles.map((r) => roles[r]).join(" · ")}</small>
          </div>
        </div>
        <div className="profile-actions">
          <button className="nav" onClick={changePassword}>
            <Icon name="key" size={18} />
            <span>Đổi mật khẩu</span>
          </button>
          <button className="nav" onClick={logout}>
            <Icon name="logout" size={18} />
            <span>Đăng xuất</span>
          </button>
        </div>
      </div>
    </div>
  );
  return (
    <div className="workspace">
      <a className="skip-link" href="#workspace-content">
        Đến nội dung chính
      </a>
      {!smallScreen && <aside className="sidebar">{navigation}</aside>}
      {smallScreen && menuOpen && (
        <Dialog
          drawer
          label="Menu điều hướng"
          onClose={() => setMenuOpen(false)}
        >
          {navigation}
        </Dialog>
      )}
      <main className="work-main">
        <header className="workspace-header">
          <div className="header-location">
            {smallScreen && (
              <button
                type="button"
                className="icon-button menu-toggle"
                aria-label="Mở menu điều hướng"
                aria-expanded={menuOpen}
                aria-controls={menuOpen ? "main-navigation" : undefined}
                onClick={() => setMenuOpen(true)}
              >
                <Icon name="menu" />
              </button>
            )}
            <span className="breadcrumb">
              Không gian nội bộ <span aria-hidden="true">/</span>{" "}
              <b>{tabs[tab]}</b>
            </span>
          </div>
          <span className="status">
            <span className={loading ? "status-dot loading" : "status-dot"} />
            {loading ? "Đang tải dữ liệu" : "Giờ Việt Nam · UTC+07"}
          </span>
        </header>
        <section className="work-content" id="workspace-content" tabIndex={-1}>
          <div className="heading">
            <div>
              <div className="eyebrow">ĐIỀU PHỐI CÔNG VIỆC</div>
              <h1>{tabs[tab]}</h1>
              <p className="muted">
                {tab === "calendar"
                  ? "Theo dõi lịch đã xác nhận. Thời gian hiển thị theo giờ Việt Nam."
                  : tab === "finder"
                    ? "Chọn thời gian và nhu cầu để tìm phòng phù hợp."
                    : {
                        new_schedule:
                          "Đăng ký cuộc họp hoặc công tác để người phụ trách xét duyệt.",
                        my_proposals:
                          "Theo dõi yêu cầu và kết quả xử lý liên quan đến bạn.",
                        review: "Xét yêu cầu trong phạm vi bạn được phân công.",
                        my_schedules:
                          "Tra cứu các hồ sơ lịch bạn được phép xem.",
                      }[tab] || "Quản lý thông tin dùng chung của đơn vị."}
              </p>
            </div>
            {isAdmin && ["rooms", "departments", "users"].includes(tab) && (
              <button
                className="compact"
                disabled={loading || busy}
                onClick={() =>
                  edit(
                    tab === "rooms"
                      ? "room"
                      : tab === "departments"
                        ? "department"
                        : "user",
                  )
                }
              >
                +{" "}
                {tab === "rooms"
                  ? "Thêm phòng họp"
                  : tab === "departments"
                    ? "Thêm phòng ban"
                    : "Cấp tài khoản"}
              </button>
            )}
          </div>
          {!editor && !scope && error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          {loading && <p role="status">Đang tải dữ liệu…</p>}
          <Scheduling
            mode={tab}
            api={api}
            user={user}
            rooms={rooms}
            departments={departments}
            directory={directory}
            loading={loading}
          />
          {tab === "reports" && (
            <UsageReport api={api} rooms={rooms} user={user} />
          )}
          {tab === "calendar" && (
            <>
              <form
                className="filter-panel"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  const filter = {
                    from: new Date(f.get("from")).toISOString(),
                    to: new Date(f.get("to")).toISOString(),
                  };
                  if (f.get("room")) filter.room_id = f.get("room");
                  if (f.get("user")) filter.user_id = f.get("user");
                  setCalendar(null);
                  run(() => calendarSearch(filter));
                }}
              >
                <label>
                  Từ (giờ máy của bạn)
                  <input
                    required
                    type="datetime-local"
                    name="from"
                    defaultValue={localInput(today)}
                  />
                </label>
                <label>
                  Đến
                  <input
                    required
                    type="datetime-local"
                    name="to"
                    defaultValue={localInput(tomorrow)}
                  />
                </label>
                <label>
                  Phòng họp
                  <select name="room" defaultValue="">
                    <option value="">Tất cả phòng</option>
                    {rooms.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.code} · {r.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Người dùng
                  <select name="user" defaultValue={user.id}>
                    <option value="">Không lọc người</option>
                    {directory.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name} · {u.employee_code}
                      </option>
                    ))}
                  </select>
                </label>
                <button disabled={busy || loading} className="compact">
                  Xem lịch
                </button>
              </form>
              <div className="info-line">
                Người liên quan và người duyệt đúng phạm vi được xem tiêu đề.
                Các lịch khác chỉ hiện bận/rảnh. Không chọn phòng/người sẽ xem
                lịch cá nhân.
              </div>
              {calendar ? (
                <>
                  <div className="section-label">
                    {calendar.total} khoảng lịch / chuyển tiếp
                  </div>
                  {calendar.items.length ? (
                    <div className="calendar-list">
                      {calendar.items.map((item) => (
                        <article
                          className={
                            "calendar-item " +
                            (item.busy_type === "BUFFER" ? "buffer" : "")
                          }
                          key={item.entry_key}
                        >
                          <div className="calendar-time">
                            {stamp(item.starts_at)}
                            <span>đến {stamp(item.ends_at)}</span>
                          </div>
                          <div>
                            <span className="tag">
                              {item.busy_type === "BUFFER"
                                ? "Chuyển tiếp"
                                : item.visibility === "DETAIL"
                                  ? item.kind === "MEETING"
                                    ? "Họp đã xác nhận"
                                    : "Công tác đã xác nhận"
                                  : "Bận"}
                            </span>
                            <h3>
                              {item.visibility === "DETAIL"
                                ? item.title
                                : item.busy_type === "BUFFER"
                                  ? "Phòng chưa sẵn sàng"
                                  : "Đã có lịch"}
                            </h3>
                            {item.room_id && (
                              <p className="muted">
                                {rooms.find((r) => r.id === item.room_id)
                                  ?.name || "Phòng họp"}
                              </p>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <Empty text="Không có lịch đã xác nhận trong khoảng đã chọn." />
                  )}
                  <Pager
                    value={calendar}
                    change={(p) => run(() => calendarSearch(calendarFilter, p))}
                  />
                </>
              ) : (
                <Empty text="Chọn khoảng thời gian rồi bấm Xem lịch." />
              )}
            </>
          )}
          {tab === "finder" && (
            <>
              <form
                className="filter-panel"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  setFound(null);
                  run(() =>
                    finderSearch({
                      starts_at: new Date(f.get("start")).toISOString(),
                      ends_at: new Date(f.get("end")).toISOString(),
                      participant_count: f.get("count"),
                      equipment_codes: f.getAll("equipment"),
                    }),
                  );
                }}
              >
                <label>
                  Bắt đầu (giờ máy của bạn)
                  <input required type="datetime-local" name="start" />
                </label>
                <label>
                  Kết thúc
                  <input required type="datetime-local" name="end" />
                </label>
                <label>
                  Số người (gồm tùy chọn)
                  <input
                    required
                    type="number"
                    min="1"
                    max="65535"
                    name="count"
                    defaultValue="2"
                  />
                </label>
                <fieldset className="equipment-select">
                  <legend>Thiết bị cần có</legend>
                  {equipmentOptions.map(([code, name]) => (
                    <label key={code} className="check">
                      <input type="checkbox" name="equipment" value={code} />
                      {name}
                    </label>
                  ))}
                </fieldset>
                <button className="compact" disabled={busy || loading}>
                  Tìm phòng
                </button>
              </form>
              <div className="info-line">
                Họp 15 phút–4 giờ, trước ít nhất 30 phút, trong 90 ngày tới. Kết
                quả tìm kiếm chưa giữ phòng; hệ thống sẽ kiểm tra lại khi gửi và
                duyệt yêu cầu.
              </div>
              {found && (
                <>
                  <div className="section-label">
                    {found.total} phòng phù hợp
                  </div>
                  <div className="room-grid">
                    {found.items.map((item) => (
                      <RoomCard
                        key={item.room.id}
                        room={item.room}
                        requestedPolicy={{
                          capacity: item.capacity_at_requested_start,
                          buffer_minutes:
                            item.buffer_minutes_at_requested_start,
                        }}
                      >
                        <span className="tag available">
                          Phù hợp thời gian đã chọn
                        </span>
                        {item.warnings.map((w, i) => (
                          <p className="warning" key={i}>
                            {w.message}
                          </p>
                        ))}
                      </RoomCard>
                    ))}
                  </div>
                  {!found.total && (
                    <Empty text="Không có phòng phù hợp. Hãy đổi thời gian, số người hoặc thiết bị." />
                  )}
                  <Pager
                    value={found}
                    change={(p) => run(() => finderSearch(finderFilter, p))}
                  />
                </>
              )}
            </>
          )}
          {["rooms", "departments", "users"].includes(tab) && (
            <>
              <div className="list-toolbar">
                <input
                  aria-label="Tìm kiếm danh mục"
                  placeholder="Tìm theo tên, mã…"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setListPage(1);
                  }}
                />
                {tab === "users" && (
                  <>
                    <select
                      aria-label="Lọc phòng ban"
                      value={accountDept}
                      onChange={(e) => {
                        setAccountDept(e.target.value);
                        setListPage(1);
                      }}
                    >
                      <option value="">Tất cả phòng ban</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name}
                        </option>
                      ))}
                    </select>
                    <select
                      aria-label="Lọc trạng thái"
                      value={accountStatus}
                      onChange={(e) => {
                        setAccountStatus(e.target.value);
                        setListPage(1);
                      }}
                    >
                      <option value="">Tất cả trạng thái</option>
                      <option value="ACTIVE">Hoạt động</option>
                      <option value="LOCKED">Đã khóa</option>
                    </select>
                  </>
                )}
                <span>{list.length} kết quả</span>
                <button
                  className="secondary compact"
                  disabled={busy}
                  onClick={() => run(load, "Đã tải lại dữ liệu mới nhất.")}
                >
                  Tải lại
                </button>
              </div>
              {tab === "rooms" ? (
                <div className="room-grid">
                  {paged.map((r) => (
                    <RoomCard key={r.id} room={r}>
                      {isAdmin && (
                        <div className="actions">
                          <button onClick={() => edit("room", r)}>
                            Sửa thông tin
                          </button>
                          <button onClick={() => edit("policy", r)}>
                            Cấu hình giờ
                          </button>
                          <button onClick={() => openScope("room", r)}>
                            Người duyệt
                          </button>
                          <button
                            onClick={() =>
                              run(async () =>
                                setHistory({
                                  room: r,
                                  items: await allPages(
                                    api,
                                    "/rooms/" + r.id + "/policies",
                                  ),
                                }),
                              )
                            }
                          >
                            Lịch sử cấu hình
                          </button>
                        </div>
                      )}
                    </RoomCard>
                  ))}
                </div>
              ) : (
                <div
                  className="table-wrap"
                  tabIndex={0}
                  role="region"
                  aria-label={
                    tab === "users"
                      ? "Danh sách tài khoản, có thể cuộn ngang"
                      : "Danh sách phòng ban, có thể cuộn ngang"
                  }
                >
                  <table>
                    <thead>
                      <tr>
                        <th>{tab === "users" ? "Nhân viên" : "Phòng ban"}</th>
                        <th>{tab === "users" ? "Phòng ban / quyền" : "Mã"}</th>
                        <th>Trạng thái</th>
                        {isAdmin && <th>Thao tác</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {paged.map((r) => (
                        <tr key={r.id}>
                          <td>
                            <b>{r.full_name || r.name}</b>
                            {tab === "users" && (
                              <small>
                                {r.employee_code} · {r.email}
                              </small>
                            )}
                          </td>
                          <td>
                            {tab === "users" ? (
                              <>
                                {
                                  departments.find(
                                    (d) => d.id === r.department_id,
                                  )?.name
                                }
                                <small>
                                  {r.roles.map((v) => roles[v]).join(" · ")}
                                </small>
                              </>
                            ) : (
                              r.code
                            )}
                          </td>
                          <td>
                            <span className="tag">
                              {tab === "users"
                                ? r.status === "ACTIVE"
                                  ? "Hoạt động"
                                  : "Đã khóa"
                                : r.accepts_new_requests
                                  ? "Đang sử dụng"
                                  : "Ngừng nhận mới"}
                            </span>
                            {r.must_change_password && (
                              <small>Cần đổi mật khẩu tạm</small>
                            )}
                          </td>
                          {isAdmin && (
                            <td className="actions">
                              <button
                                onClick={() =>
                                  edit(
                                    tab === "users" ? "user" : "department",
                                    r,
                                  )
                                }
                              >
                                Sửa
                              </button>
                              {tab === "users" ? (
                                <button onClick={() => edit("reset", r)}>
                                  Đặt lại mật khẩu
                                </button>
                              ) : (
                                <button
                                  onClick={() => openScope("department", r)}
                                >
                                  Người duyệt
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!paged.length && !loading && (
                <Empty text="Không có dữ liệu phù hợp." />
              )}
              <Pager
                value={{ total: list.length, page: listPage, page_size: 12 }}
                change={setListPage}
              />
            </>
          )}
        </section>
      </main>
      {editor && draft && (
        <Dialog labelledBy="editor-title" busy={busy} onClose={closeEditor}>
          <div className="modal-heading">
            <h2 id="editor-title">
              {
                {
                  user: editor.row ? "Cập nhật tài khoản" : "Cấp tài khoản",
                  department: editor.row
                    ? "Cập nhật phòng ban"
                    : "Thêm phòng ban",
                  room: editor.row ? "Cập nhật phòng họp" : "Thêm phòng họp",
                  policy: "Thêm phiên bản cấu hình",
                  reset: "Đặt lại mật khẩu tạm",
                }[editor.kind]
              }
            </h2>
            <button
              type="button"
              className="text-button"
              disabled={busy}
              onClick={closeEditor}
            >
              Đóng ×
            </button>
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          <form onSubmit={save}>
            <fieldset disabled={busy} className="plain-fieldset">
              {editor.kind === "user" && (
                <>
                  <div className="form-grid">
                    <label>
                      Mã nhân viên
                      <input
                        required
                        maxLength={32}
                        value={draft.employee_code}
                        onChange={(e) =>
                          patch({ employee_code: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      Họ tên
                      <input
                        required
                        maxLength={150}
                        value={draft.full_name}
                        onChange={(e) => patch({ full_name: e.target.value })}
                      />
                    </label>
                    <label>
                      Email
                      <input
                        required
                        type="email"
                        value={draft.email}
                        onChange={(e) => patch({ email: e.target.value })}
                      />
                    </label>
                    <label>
                      Phòng ban
                      <select
                        required
                        value={draft.department_id}
                        onChange={(e) =>
                          patch({ department_id: e.target.value })
                        }
                      >
                        <option value="">Chọn phòng ban</option>
                        {departments
                          .filter(
                            (d) =>
                              d.accepts_new_requests ||
                              d.id === draft.department_id,
                          )
                          .map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Trạng thái
                      <select
                        value={draft.status}
                        onChange={(e) => patch({ status: e.target.value })}
                      >
                        <option value="ACTIVE">Hoạt động</option>
                        <option value="LOCKED">Đã khóa</option>
                      </select>
                    </label>
                    {!editor.row && (
                      <label>
                        Mật khẩu tạm
                        <input
                          type="password"
                          autoComplete="new-password"
                          minLength={12}
                          maxLength={128}
                          required
                          value={draft.temporary_password}
                          onChange={(e) =>
                            patch({ temporary_password: e.target.value })
                          }
                        />
                      </label>
                    )}
                  </div>
                  <fieldset>
                    <legend>Nhóm quyền (chọn ít nhất một)</legend>
                    {Object.entries(roles).map(([value, title]) => (
                      <label className="check" key={value}>
                        <input
                          type="checkbox"
                          checked={draft.roles.includes(value)}
                          onChange={(e) =>
                            patch({
                              roles: e.target.checked
                                ? [...draft.roles, value]
                                : draft.roles.filter((r) => r !== value),
                            })
                          }
                        />
                        {title}
                      </label>
                    ))}
                  </fieldset>
                  <p className="info-line">
                    Người phê duyệt cần được phân công thêm tại từng phòng
                    họp/phòng ban. Đổi quyền, trạng thái, email hoặc phòng ban
                    sẽ kết thúc các phiên đăng nhập của tài khoản này.
                  </p>
                </>
              )}
              {["department", "room"].includes(editor.kind) && (
                <>
                  <div className="form-grid">
                    <label>
                      Mã
                      <input
                        required
                        maxLength={32}
                        value={draft.code}
                        onChange={(e) => patch({ code: e.target.value })}
                      />
                    </label>
                    <label>
                      Tên
                      <input
                        required
                        maxLength={150}
                        value={draft.name}
                        onChange={(e) => patch({ name: e.target.value })}
                      />
                    </label>
                    {editor.kind === "room" && (
                      <label>
                        Vị trí
                        <input
                          required
                          maxLength={255}
                          value={draft.location}
                          onChange={(e) => patch({ location: e.target.value })}
                        />
                      </label>
                    )}
                  </div>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={draft.accepts_new_requests}
                      onChange={(e) =>
                        patch({ accepts_new_requests: e.target.checked })
                      }
                    />
                    Cho phép nhận yêu cầu mới
                  </label>
                  <p className="muted">
                    Ngừng nhận mới vẫn giữ nguyên lịch đã được duyệt và dữ liệu
                    lịch sử.
                  </p>
                </>
              )}
              {editor.kind === "room" && (
                <>
                  <EquipmentFields
                    value={draft.equipment}
                    onChange={(equipment) => patch({ equipment })}
                  />
                  {!editor.row && (
                    <PolicyFields
                      value={draft.initial_policy}
                      onChange={(initial_policy) => patch({ initial_policy })}
                    />
                  )}
                </>
              )}
              {editor.kind === "policy" && (
                <>
                  <div className="info-line">
                    Cấu hình được lưu thành phiên bản mới. Hệ thống từ chối thay
                    đổi làm lịch đã duyệt vượt sức chứa, ngoài giờ phục vụ hoặc
                    chồng khoảng chuyển tiếp.
                  </div>
                  <PolicyFields value={draft} onChange={setDraft} />
                </>
              )}
              {editor.kind === "reset" && (
                <>
                  <p>
                    Đặt mật khẩu tạm cho <b>{editor.row.full_name}</b>. Người
                    dùng phải đổi lại sau khi đăng nhập; các phiên hiện tại sẽ
                    kết thúc.
                  </p>
                  <label>
                    Mật khẩu tạm mới
                    <input
                      type="password"
                      required
                      minLength={12}
                      maxLength={128}
                      autoComplete="new-password"
                      value={draft.new_temporary_password}
                      onChange={(e) =>
                        patch({ new_temporary_password: e.target.value })
                      }
                    />
                  </label>
                </>
              )}
              <div className="modal-footer">
                <button
                  type="button"
                  className="secondary compact"
                  onClick={closeEditor}
                >
                  Hủy
                </button>
                <button
                  className="compact"
                  disabled={editor.kind === "user" && !draft.roles.length}
                >
                  {busy ? "Đang lưu…" : "Lưu thay đổi"}
                </button>
              </div>
            </fieldset>
          </form>
        </Dialog>
      )}
      {scope && (
        <Dialog
          labelledBy="scope-title"
          busy={busy}
          onClose={() => {
            setScope(null);
            setError("");
          }}
        >
          <div className="modal-heading">
            <h2 id="scope-title">Người duyệt · {scope.row.name}</h2>
            <button
              className="text-button"
              disabled={busy}
              onClick={() => {
                setScope(null);
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
          <p className="info-line">
            Có {scope.value.pending_proposal_count} yêu cầu đang chờ trong phạm
            vi này. Việc phân công sẽ áp dụng cho các lần xử lý tiếp theo.
          </p>
          <form onSubmit={saveScope}>
            <fieldset disabled={busy}>
              <legend>Tài khoản đủ điều kiện</legend>
              {accounts
                .filter(
                  (u) => u.status === "ACTIVE" && u.roles.includes("APPROVER"),
                )
                .map((u) => (
                  <label className="check" key={u.id}>
                    <input
                      type="checkbox"
                      checked={scope.selected.includes(u.id)}
                      onChange={(e) =>
                        setScope({
                          ...scope,
                          selected: e.target.checked
                            ? [...scope.selected, u.id]
                            : scope.selected.filter((id) => id !== u.id),
                        })
                      }
                    />
                    {u.full_name} · {u.employee_code}
                  </label>
                ))}
            </fieldset>
            {!scope.selected.length && (
              <p className="warning">
                Không còn người duyệt được phân công. Các yêu cầu cần người
                duyệt sẽ chưa thể được xử lý.
              </p>
            )}
            <p className="muted">
              Người gửi không được tự duyệt yêu cầu của mình. Nên phân công ít
              nhất hai người để có người duyệt thay.
            </p>
            <div className="modal-footer">
              <button
                type="button"
                className="secondary compact"
                disabled={busy}
                onClick={() => {
                  setScope(null);
                  setError("");
                }}
              >
                Hủy
              </button>
              <button className="compact" disabled={busy}>
                Lưu phân công
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {history && (
        <Dialog label="Lịch sử cấu hình" onClose={() => setHistory(null)}>
          <div className="modal-heading">
            <h2>Cấu hình · {history.room.name}</h2>
            <button className="text-button" onClick={() => setHistory(null)}>
              Đóng ×
            </button>
          </div>
          {history.items.map((p) => (
            <article className="policy-history" key={p.id}>
              <h3>Từ {stamp(p.effective_from)}</h3>
              <p>
                {p.capacity} người · Chuyển tiếp {p.buffer_minutes} phút
              </p>
              {weekdays.map((day, n) => (
                <p key={day}>
                  <b>{day}:</b>{" "}
                  {p.weekly_windows
                    .filter((w) => w.weekday === n + 1)
                    .map((w) => `${w.start_time}–${w.end_time}`)
                    .join(", ") || "Nghỉ"}
                </p>
              ))}
              {p.calendar_days.map((d) => (
                <p key={d.local_date}>
                  {d.local_date} · {d.reason} ·{" "}
                  {d.is_closed
                    ? "Nghỉ"
                    : d.windows
                        .map((w) => `${w.start_time}–${w.end_time}`)
                        .join(", ")}
                </p>
              ))}
            </article>
          ))}
        </Dialog>
      )}
    </div>
  );
}
function Empty({ text }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name="calendar" size={28} />
      </span>
      <p>{text}</p>
    </div>
  );
}
function RoomCard({ room, requestedPolicy, children }) {
  const p = requestedPolicy || room.effective_policy;
  return (
    <article className="room-card">
      <div className="room-top">
        <span className="room-code">{room.code}</span>
        <span
          className={"tag " + (room.accepts_new_requests ? "available" : "")}
        >
          {room.accepts_new_requests ? "Nhận đặt mới" : "Ngừng nhận mới"}
        </span>
      </div>
      <h3>{room.name}</h3>
      <p className="muted">{room.location}</p>
      <div className="room-specs">
        <span>
          <Icon name="users" size={17} />
          {p ? p.capacity + " người" : "Chưa có cấu hình hiệu lực"}
        </span>
        {p && (
          <span>
            <Icon name="clock" size={17} />
            Đệm {p.buffer_minutes} phút
          </span>
        )}
      </div>
      <div className="equipment-tags">
        {room.equipment.map((e) => (
          <span key={e.equipment_code}>
            {e.display_name} ×{e.quantity}
          </span>
        ))}
      </div>
      {children}
    </article>
  );
}
