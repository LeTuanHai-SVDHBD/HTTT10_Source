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
      const query = new URLSearchParams({
        from: new Date(from + "T00:00:00").toISOString(),
        to: new Date(to + "T00:00:00").toISOString(),
      });
      selected.forEach((id) => query.append("room_ids", id));
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
    <section>
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
        <label>
          Phòng trong báo cáo
          <select
            multiple
            size={Math.min(5, Math.max(2, allowed.length))}
            disabled={busy}
            value={selected}
            onChange={(e) =>
              update(
                setSelected,
                Array.from(e.target.selectedOptions, (o) => o.value),
              )
            }
          >
            {allowed.map((r) => (
              <option key={r.id} value={r.id}>
                {r.code} · {r.name}
              </option>
            ))}
          </select>
          <small>
            Không chọn nghĩa là tất cả phòng trong phạm vi được phép. Tối đa 366
            ngày.
          </small>
        </label>
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
          <p>
            Khoảng báo cáo: {stamp(report.period_from)} →{" "}
            {stamp(report.period_to)}. Lập lúc {stamp(report.generated_at)}.
          </p>
          {!report.rooms.length && (
            <p>Không có phòng trong phạm vi báo cáo hiện tại.</p>
          )}
          <div className="table-wrap">
            <table>
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
