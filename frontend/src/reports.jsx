import React, { useState } from "react";
import { stamp } from "./api";

export default function UsageReport({ api, rooms, user }) {
  const today = new Date();
  const date = (d) =>
    new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 10);
  const [from, setFrom] = useState(date(today));
  const [to, setTo] = useState(date(new Date(today.getTime() + 7 * 86400000)));
  const [selected, setSelected] = useState([]);
  const [allRooms, setAllRooms] = useState(true);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const allowed = user.roles.includes("ADMIN")
    ? rooms
    : rooms.filter((r) => user.room_scope_ids.includes(r.id));
  const update = (setter, value) => {
    setter(value);
    setReport(null);
    setError("");
  };
  async function run(e) {
    e.preventDefault();
    setReport(null);
    setError("");
    setBusy(true);
    try {
      if (from >= to) throw new Error("Ngày kết thúc phải sau ngày bắt đầu.");
      if (!allRooms && !selected.length)
        throw new Error("Chọn ít nhất một phòng để xem báo cáo.");
      const query = new URLSearchParams({
        from: new Date(from + "T00:00:00").toISOString(),
        to: new Date(to + "T00:00:00").toISOString(),
      });
      if (!allRooms) selected.forEach((id) => query.append("room_ids", id));
      setReport(await api("/reports/room-usage?" + query));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const hours = (value) =>
    Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 2 });
  const rate = (value) =>
    value === null ? "Không áp dụng" : hours(value) + "%";
  function cells(m) {
    return (
      <>
        <td>{m.confirmed_count}</td>
        <td>{m.cancelled_count}</td>
        <td>{hours(m.meeting_hours)}</td>
        <td>{hours(m.buffer_hours)}</td>
        <td>{hours(m.service_hours)}</td>
        <td>{rate(m.planned_rate_percent)}</td>
      </>
    );
  }
  return (
    <section className="usage-panel">
      <p className="info-line">
        Số liệu theo kế hoạch đặt phòng, không chứng minh phòng đã được sử dụng
        thực tế. Tỷ lệ chỉ tính giờ họp trong giờ phục vụ; thời gian chuyển tiếp
        được báo riêng.
      </p>
      <form className="filter-panel report-filters" onSubmit={run}>
        <label>
          Từ ngày
          <input
            type="date"
            required
            disabled={busy}
            value={from}
            onChange={(e) => update(setFrom, e.target.value)}
          />
        </label>
        <label>
          Đến ngày (không gồm ngày này)
          <input
            type="date"
            required
            disabled={busy}
            value={to}
            onChange={(e) => update(setTo, e.target.value)}
          />
        </label>
        <fieldset className="report-room-picker" disabled={busy}>
          <legend>Phòng trong báo cáo</legend>
          <label className="check">
            <input
              type="radio"
              name="report-room-mode"
              checked={allRooms}
              onChange={() => update(setAllRooms, true)}
            />
            Tất cả phòng được phép
          </label>
          <label className="check">
            <input
              type="radio"
              name="report-room-mode"
              checked={!allRooms}
              onChange={() => update(setAllRooms, false)}
            />
            Chọn phòng cụ thể
          </label>
          {!allRooms && (
            <div className="report-room-options">
              {allowed.map((r) => (
                <label className="check" key={r.id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(r.id)}
                    onChange={(e) =>
                      update(
                        setSelected,
                        e.target.checked
                          ? [...selected, r.id]
                          : selected.filter((id) => id !== r.id),
                      )
                    }
                  />
                  {r.code} · {r.name}
                </label>
              ))}
            </div>
          )}
          <small>
            Tối đa 366 ngày. Chỉ tổng hợp phòng trong phạm vi của bạn.
          </small>
        </fieldset>
        <button className="compact" disabled={busy}>
          {busy ? "Đang tính…" : "Xem báo cáo"}
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {report && (
        <>
          <div className="report-metrics" aria-label="Tổng quan báo cáo">
            <div className="metric-card">
              <span>Lượt đã xác nhận</span>
              <strong>{report.total.confirmed_count}</strong>
              <small>Trong khoảng đang xem</small>
            </div>
            <div className="metric-card">
              <span>Tổng giờ họp</span>
              <strong>
                {hours(report.total.meeting_hours)} <small>giờ</small>
              </strong>
              <small>Không tính thời gian chuyển tiếp</small>
            </div>
            <div className="metric-card">
              <span>Tỷ lệ theo kế hoạch</span>
              <strong>{rate(report.total.planned_rate_percent)}</strong>
              <small>Theo tổng giờ phục vụ</small>
            </div>
            <div className="metric-card">
              <span>Lượt đã hủy</span>
              <strong>{report.total.cancelled_count}</strong>
              <small>Không cộng vào giờ họp</small>
            </div>
          </div>
          <p>
            Khoảng báo cáo: {stamp(report.period_from)} →{" "}
            {stamp(report.period_to)}. Lập lúc {stamp(report.generated_at)}.
          </p>
          {!report.rooms.length && (
            <p>Không có phòng trong phạm vi báo cáo hiện tại.</p>
          )}
          <p className="table-hint">
            Có thể cuộn ngang bảng để xem đầy đủ các chỉ số.
          </p>
          <div
            className="table-wrap"
            role="region"
            aria-label="Số liệu phòng, có thể cuộn ngang"
            tabIndex={0}
          >
            <table className="usage-table">
              <caption>Báo cáo sử dụng phòng theo kế hoạch</caption>
              <thead>
                <tr>
                  <th>Phòng</th>
                  <th>Đã xác nhận</th>
                  <th>Đã hủy</th>
                  <th>Giờ họp</th>
                  <th>Giờ chuyển tiếp</th>
                  <th>Giờ phục vụ</th>
                  <th>Tỷ lệ theo kế hoạch</th>
                </tr>
              </thead>
              <tbody>
                {report.rooms.map((r) => (
                  <tr key={r.room_id}>
                    <th scope="row">
                      {rooms.find((room) => room.id === r.room_id)?.code ||
                        "Phòng"}
                    </th>
                    {cells(r)}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Tổng trong phạm vi</th>
                  {cells(report.total)}
                </tr>
              </tfoot>
            </table>
          </div>
          <p className="muted">
            Tỷ lệ tổng cộng giờ họp trong giờ phục vụ rồi chia tổng giờ phục vụ,
            không lấy trung bình các phần trăm. Không gồm lịch hủy, bản lịch đã
            thay thế hoặc thời gian chuyển tiếp. Mẫu số bằng 0: Không áp dụng.
          </p>
        </>
      )}
    </section>
  );
}
