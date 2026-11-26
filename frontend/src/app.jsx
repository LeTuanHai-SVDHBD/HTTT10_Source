import React, { useEffect, useRef, useState } from "react";
import { client } from "./api";
import Workspace from "./workspace";
import { Icon, PasswordField } from "./ui";

const authApi = client();

export default function App() {
  const [user, setUser] = useState(null);
  const activeUser = useRef(null);
  const [restoreState, setRestoreState] = useState("loading");
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false),
    [changing, setChanging] = useState(false);

  function updateUser(user) {
    activeUser.current = user;
    setUser(user);
    setChanging(Boolean(user?.must_change_password));
  }

  useEffect(() => {
    if (restoreState !== "loading") return;
    let active = true;
    authApi("/auth/me")
      .then((me) => {
        if (!active) return;
        updateUser(me);
        setRestoreState("ready");
      })
      .catch((e) => {
        if (!active) return;
        setRestoreState(e.status === 401 ? "ready" : "failed");
      });
    return () => {
      active = false;
    };
  }, [restoreState]);

  const api = client({
    userId: user?.id,
    onExpired: () => {
      if (!user || activeUser.current !== user) return;
      updateUser(null);
      setError("");
      setNotice("Phiên đăng nhập không còn hợp lệ. Vui lòng đăng nhập lại.");
    },
  });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const f = new FormData(event.currentTarget);
    try {
      if (!user) {
        await authApi("/auth/login", "POST", {
          email: f.get("email"),
          password: f.get("password"),
        });
        setRestoreState("loading");
      } else {
        await api("/auth/password", "PUT", {
          current_password: f.get("current"),
          new_password: f.get("new"),
          confirm_password: f.get("confirm"),
        });
        updateUser(null);
        setNotice("Đã đổi mật khẩu. Vui lòng đăng nhập lại.");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    let message = "Đã đăng xuất.";
    try {
      await api("/auth/logout", "POST");
    } catch (e) {
      if (e.status !== 401)
        throw new Error("Chưa đăng xuất được. Vui lòng thử lại.");
      message = e.message;
    }
    updateUser(null);
    setError("");
    setNotice(message);
  }

  if (restoreState !== "ready")
    return (
      <main className="auth-section" aria-busy={restoreState === "loading"}>
        {restoreState === "loading" ? (
          <p role="status">Đang kiểm tra phiên đăng nhập…</p>
        ) : (
          <>
            <p role="alert">Không kiểm tra được phiên đăng nhập.</p>
            <button type="button" onClick={() => setRestoreState("loading")}>
              Thử lại
            </button>
          </>
        )}
      </main>
    );

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
          <span className="brand-mark">
            <Icon name="calendar" size={26} />
          </span>
          <b>
            HTTT10<span>Lịch công tác nội bộ</span>
          </b>
        </div>
        <p className="login-kicker">MỘT NƠI CHO MỌI KẾ HOẠCH</p>
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
        <div className="login-footnote">
          <Icon name="shield" size={18} />
          <small>Không gian riêng cho đơn vị của bạn</small>
        </div>
      </aside>
      <main>
        <header>
          <span>Cổng nội bộ</span>
          <span className="status">
            <span className="status-dot" />
            Lịch công tác & phòng họp
          </span>
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
          <form
            onSubmit={submit}
            key={user ? "change" : "login"}
            aria-busy={busy}
          >
            <fieldset disabled={busy} className="plain-fieldset">
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
                  <PasswordField
                    label="Mật khẩu"
                    id="login-password"
                    name="password"
                    required
                    maxLength={128}
                    autoComplete="current-password"
                  />
                </>
              ) : (
                <>
                  <PasswordField
                    label="Mật khẩu hiện tại"
                    id="current-password"
                    name="current"
                    required
                    maxLength={128}
                    autoComplete="current-password"
                  />
                  <PasswordField
                    label="Mật khẩu mới"
                    id="new-password"
                    name="new"
                    required
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                  />
                  <PasswordField
                    label="Xác nhận mật khẩu mới"
                    id="confirm-password"
                    name="confirm"
                    required
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                  />
                  <small>Từ 12 đến 128 ký tự.</small>
                </>
              )}
              <button disabled={busy}>
                {busy ? "Đang xử lý…" : user ? "Lưu mật khẩu mới" : "Đăng nhập"}
                {!busy && <Icon name="arrow" size={19} />}
              </button>
            </fieldset>
          </form>
          {user && !user.must_change_password && (
            <button className="secondary" onClick={() => setChanging(false)}>
              Quay lại
            </button>
          )}
          {user && (
            <button
              className="secondary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await logout();
                } catch (e) {
                  setError(e.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Đăng xuất
            </button>
          )}
          <footer>Tài khoản nội bộ được cấp bởi quản trị viên.</footer>
        </section>
      </main>
    </div>
  );
}
