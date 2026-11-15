import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { client, roles } from "./api";
import Workspace from "./workspace";
import "./style.css";

function App() {
  const [token, setToken] = useState(null),
    [user, setUser] = useState(null);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false),
    [changing, setChanging] = useState(false);
  const clear = () => {
    setToken(null);
    setUser(null);
    setChanging(false);
  };
  const api = client(token, clear);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const f = new FormData(event.currentTarget);
    try {
      if (!user) {
        const t = await api("/auth/login", "POST", {
          email: f.get("email"),
          password: f.get("password"),
        });
        const me = await client(t.access_token, clear)("/auth/me");
        setToken(t.access_token);
        setUser(me);
        setChanging(me.must_change_password);
      } else {
        await api("/auth/password", "PUT", {
          current_password: f.get("current"),
          new_password: f.get("new"),
          confirm_password: f.get("confirm"),
        });
        clear();
        setNotice("Đã đổi mật khẩu. Vui lòng đăng nhập lại.");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    setBusy(true);
    let message = "Đã đăng xuất.";
    try {
      await api("/auth/logout", "POST");
    } catch {
      message =
        "Đã dọn phiên trên trình duyệt; chưa xác nhận thu hồi phía máy chủ.";
    }
    clear();
    setBusy(false);
    setError("");
    setNotice(message);
  }
  if (user && !changing)
    return (
      <Workspace
        api={api}
        user={user}
        logout={logout}
        changePassword={() => {
          setChanging(true);
          setError("");
        }}
      />
    );
  return (
    <div className="shell">
      <aside className="login-aside">
        <div className="brand">
          ▦ <b>HTTT10</b>
        </div>
        <p>LỊCH CÔNG TÁC NỘI BỘ</p>
        <div className="aside-content">
          <span className="pill">Không gian làm việc chung</span>
          <h1>
            Sắp xếp lịch.
            <br />
            Kết nối công việc.
          </h1>
          <p>
            Tra cứu lịch, tìm phòng phù hợp và quản lý tài nguyên của đơn vị.
          </p>
        </div>
        <small>Lịch công tác & phòng họp</small>
      </aside>
      <main>
        <header>
          <span>Cổng nội bộ</span>
          <span className="status">● Hệ thống quản lý lịch</span>
        </header>
        <section className="auth-section">
          <div className="eyebrow">
            {user ? "BẢO MẬT TÀI KHOẢN" : "CHÀO MỪNG TRỞ LẠI"}
          </div>
          <h2>{!user ? "Đăng nhập" : "Đổi mật khẩu"}</h2>
          <p className="intro">
            {!user
              ? "Dùng tài khoản được quản trị viên cấp."
              : user.must_change_password
                ? "Bạn cần đổi mật khẩu tạm trước khi dùng hệ thống."
                : "Đổi mật khẩu sẽ kết thúc các phiên đăng nhập."}
          </p>
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
          <form onSubmit={submit} key={user ? "change" : "login"}>
            {!user ? (
              <>
                <label>
                  Email nội bộ
                  <input
                    type="email"
                    name="email"
                    required
                    autoComplete="username"
                    placeholder="ban@donvi.vn"
                  />
                </label>
                <label>
                  Mật khẩu
                  <input
                    type="password"
                    name="password"
                    required
                    maxLength={128}
                    autoComplete="current-password"
                  />
                </label>
              </>
            ) : (
              <>
                <label>
                  Mật khẩu hiện tại
                  <input
                    type="password"
                    name="current"
                    required
                    maxLength={128}
                    autoComplete="current-password"
                  />
                </label>
                <label>
                  Mật khẩu mới
                  <input
                    type="password"
                    name="new"
                    required
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  Xác nhận mật khẩu mới
                  <input
                    type="password"
                    name="confirm"
                    required
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                  />
                </label>
                <small>Từ 12 đến 128 ký tự.</small>
              </>
            )}
            <button disabled={busy}>
              {busy ? "Đang xử lý…" : user ? "Lưu mật khẩu mới" : "Đăng nhập"}
            </button>
          </form>
          {user && !user.must_change_password && (
            <button className="secondary" onClick={() => setChanging(false)}>
              Quay lại
            </button>
          )}
          {user && (
            <button className="secondary" disabled={busy} onClick={logout}>
              Đăng xuất
            </button>
          )}
          <footer>Tài khoản nội bộ được cấp bởi quản trị viên.</footer>
        </section>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
