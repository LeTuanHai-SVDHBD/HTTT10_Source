// Frontend interaction checks. No API, database or SMTP credentials are used.
const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const { buildSync } = require("esbuild");
const dom = new JSDOM(
  '<!doctype html><html><body><div id="root"></div></body></html>',
  { url: "http://localhost/" },
);
for (const key of [
  "window",
  "document",
  "navigator",
  "HTMLElement",
  "HTMLInputElement",
  "Event",
  "KeyboardEvent",
  "MouseEvent",
  "MutationObserver",
  "FormData",
])
  Object.defineProperty(globalThis, key, {
    value: dom.window[key],
    configurable: true,
    writable: true,
  });
global.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
global.IS_REACT_ACT_ENVIRONMENT = true;
let width = 1280;
const mediaQueries = new Set();
window.matchMedia = (query) => {
  const listeners = new Set();
  const value = {
    media: query,
    get matches() {
      return width <= 1023;
    },
    addEventListener(type, fn) {
      listeners.add(fn);
    },
    removeEventListener(type, fn) {
      listeners.delete(fn);
    },
    dispatch() {
      listeners.forEach((fn) => fn({ matches: value.matches }));
    },
    listeners,
  };
  mediaQueries.add(value);
  return value;
};
const React = require("react");
const h = React.createElement;
const {
  render,
  screen,
  within,
  fireEvent,
  waitFor,
  cleanup,
  act,
} = require("@testing-library/react");
const userEvent = require("@testing-library/user-event").default;
const cache = path.resolve(__dirname, "../node_modules/.cache/httt10-ui");
fs.mkdirSync(cache, { recursive: true });
buildSync({
  stdin: {
    contents:
      'export {Dialog,PasswordField,useSmallScreen} from "./ui.jsx"; export {default as App} from "./app.jsx"; export {default as Workspace} from "./workspace.jsx"; export {default as UsageReport} from "./reports.jsx";',
    resolveDir: path.resolve(__dirname, "../src"),
    sourcefile: "ui-test-entry.jsx",
  },
  bundle: true,
  platform: "node",
  format: "cjs",
  external: ["react", "react-dom", "react-dom/client"],
  outfile: path.join(cache, "components.cjs"),
});
const {
  Dialog,
  PasswordField,
  useSmallScreen,
  App,
  Workspace,
  UsageReport,
} = require(path.join(cache, "components.cjs"));
const renderUI = (value) =>
  render(value, { container: document.getElementById("root") });
const user = () => userEvent.setup({ document });
const setWidth = (value) => {
  width = value;
  mediaQueries.forEach((m) => m.dispatch());
};
beforeEach(() => {
  document.body.innerHTML = '<div id="root"></div>';
  document.body.style.overflow = "";
  width = 1280;
  window.history.replaceState({}, "", "/");
});
afterEach(() => cleanup());

test("Password visibility retains the entered value and never submits the form", async () => {
  let submits = 0;
  renderUI(
    h(
      "form",
      {
        onSubmit: (e) => {
          e.preventDefault();
          submits++;
        },
      },
      h(PasswordField, {
        label: "Mật khẩu",
        id: "password",
        name: "password",
        required: true,
      }),
    ),
  );
  const input = screen.getByLabelText("Mật khẩu", { exact: true });
  await user().type(input, "Test-Password-2026");
  assert.equal(input.type, "password");
  await user().click(
    screen.getByRole("button", { name: "Hiện mật khẩu", exact: true }),
  );
  assert.equal(input.type, "text");
  assert.equal(input.value, "Test-Password-2026");
  assert.equal(new FormData(input.form).get("password"), "Test-Password-2026");
  assert.equal(submits, 0);
  await user().click(
    screen.getByRole("button", { name: "Ẩn mật khẩu", exact: true }),
  );
  assert.equal(input.type, "password");
});

test("Dialog traps Tab, closes on Escape and restores focus and page scrolling", async () => {
  function Fixture() {
    const [open, setOpen] = React.useState(false);
    return h(
      React.Fragment,
      null,
      h("button", { onClick: () => setOpen(true) }, "Mở hộp thoại"),
      open &&
        h(
          Dialog,
          { label: "Biểu mẫu", onClose: () => setOpen(false) },
          h("button", null, "Đầu tiên"),
          h("input", { "aria-label": "Nội dung" }),
          h("button", null, "Cuối cùng"),
        ),
    );
  }
  renderUI(h(Fixture));
  const opener = screen.getByRole("button", { name: "Mở hộp thoại" });
  await user().click(opener);
  const dialog = screen.getByRole("dialog", { name: "Biểu mẫu" });
  assert.ok(document.activeElement === dialog, "dialog receives focus");
  assert.equal(document.body.style.overflow, "hidden");
  assert.equal(document.getElementById("root").inert, true);
  fireEvent.keyDown(document, { key: "Tab" });
  assert.equal(
    document.activeElement,
    within(dialog).getByRole("button", { name: "Đầu tiên" }),
  );
  fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
  assert.equal(
    document.activeElement,
    within(dialog).getByRole("button", { name: "Cuối cùng" }),
  );
  fireEvent.keyDown(document, { key: "Tab" });
  assert.equal(
    document.activeElement,
    within(dialog).getByRole("button", { name: "Đầu tiên" }),
  );
  fireEvent.keyDown(document, { key: "Escape" });
  assert.ok(screen.queryByRole("dialog") === null, "dialog should close");
  assert.ok(document.activeElement === opener, "focus returns to opener");
  assert.equal(document.body.style.overflow, "");
  assert.equal(document.getElementById("root").inert, false);
});

test("Escape closes only the top warning and preserves the underlying dialog", async () => {
  function Fixture() {
    const [open, setOpen] = React.useState(false),
      [nested, setNested] = React.useState(false);
    return h(
      React.Fragment,
      null,
      h("button", { onClick: () => setOpen(true) }, "Mở hồ sơ"),
      open &&
        h(
          Dialog,
          { label: "Hồ sơ", onClose: () => setOpen(false) },
          h("button", { onClick: () => setNested(true) }, "Mở cảnh báo"),
          nested &&
            h(
              Dialog,
              { label: "Cảnh báo", onClose: () => setNested(false) },
              h("button", null, "Xác nhận"),
            ),
        ),
    );
  }
  renderUI(h(Fixture));
  await user().click(screen.getByRole("button", { name: "Mở hồ sơ" }));
  await user().click(screen.getByRole("button", { name: "Mở cảnh báo" }));
  assert.equal(screen.getAllByRole("dialog").length, 2);
  fireEvent.keyDown(document, { key: "Escape" });
  assert.ok(
    screen.queryByRole("dialog", { name: "Cảnh báo" }) === null,
    "warning closed",
  );
  assert.ok(screen.getByRole("dialog", { name: "Hồ sơ" }));
  assert.equal(document.getElementById("root").inert, true);
  fireEvent.keyDown(document, { key: "Escape" });
  assert.ok(
    document.querySelector('[role="dialog"]') === null,
    "dialog should close",
  );
  assert.equal(document.getElementById("root").inert, false);
});

test("A busy operation cannot be dismissed with Escape", () => {
  let closed = 0;
  const view = renderUI(
    h(
      Dialog,
      { label: "Đang lưu", busy: true, onClose: () => closed++ },
      h("p", null, "Đang xử lý"),
    ),
  );
  fireEvent.keyDown(document, { key: "Escape" });
  assert.equal(closed, 0);
  view.rerender(
    h(
      Dialog,
      { label: "Đang lưu", busy: false, onClose: () => closed++ },
      h("p", null, "Đã xử lý"),
    ),
  );
  fireEvent.keyDown(document, { key: "Escape" });
  assert.equal(closed, 1);
});

test("Responsive navigation reacts to the breakpoint and removes its listener", () => {
  function Probe() {
    const small = useSmallScreen();
    return h("output", null, small ? "mobile" : "desktop");
  }
  const view = renderUI(h(Probe));
  assert.equal(screen.getByRole("status").textContent, "desktop");
  act(() => setWidth(390));
  assert.equal(screen.getByRole("status").textContent, "mobile");
  act(() => setWidth(1280));
  assert.equal(screen.getByRole("status").textContent, "desktop");
  view.unmount();
  assert.equal(
    [...mediaQueries].reduce((n, m) => n + m.listeners.size, 0),
    0,
  );
});

const room = {
  id: "room-a",
  code: "A101",
  name: "Phòng họp A101",
  location: "Tầng 1",
  accepts_new_requests: true,
  row_version: 1,
  effective_policy: { capacity: 20, buffer_minutes: 15 },
  equipment: [],
};
const account = {
  id: "user-a",
  employee_code: "NV01",
  full_name: "Nguyễn Minh Anh",
  department_id: "hc",
  roles: ["ADMIN", "EMPLOYEE", "APPROVER"],
  room_scope_ids: ["room-a"],
};
const page = (items) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 100,
});
async function workspaceApi(path) {
  return path.startsWith("/rooms?")
    ? page([room])
    : path.startsWith("/departments?")
      ? page([
          {
            id: "hc",
            name: "Hành chính",
            code: "HC",
            accepts_new_requests: true,
          },
        ])
      : page([]);
}

test("Reload restores the web session and logout ends it", async (t) => {
  let signedIn = false;
  let logoutAvailable = false;
  const fetch = t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(options.headers["X-HTTT10-Web"], "1");
    assert.equal(options.headers.Authorization, undefined);
    const path = url.replace(/^\/api\/v1/, "");
    if (path === "/auth/login") {
      signedIn = true;
      return Response.json({ expires_in: 28800 });
    }
    if (!signedIn) return Response.json({}, { status: 401 });
    if (path === "/auth/me") return Response.json(account);
    assert.equal(options.headers["X-HTTT10-User"], account.id);
    if (path === "/auth/logout") {
      if (!logoutAvailable) return Response.json({}, { status: 503 });
      signedIn = false;
      return new Response(null, { status: 204 });
    }
    return Response.json(await workspaceApi(path));
  });

  const initial = renderUI(h(App));
  await screen.findByRole("heading", { name: "Đăng nhập" });
  fireEvent.change(screen.getByLabelText("Email nội bộ"), {
    target: { value: "nv01@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Mật khẩu", { exact: true }), {
    target: { value: "Example-Only-Test" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
  await screen.findByText(account.full_name);

  initial.unmount();
  document.body.innerHTML = '<div id="root"></div>';
  const reloaded = renderUI(h(App));
  await screen.findByText(account.full_name);
  assert.equal(
    fetch.mock.calls.filter(({ arguments: [url] }) => url.endsWith("/auth/login")).length,
    1,
  );
  await user().click(screen.getByRole("button", { name: "Đăng xuất" }));
  await screen.findByText("Chưa đăng xuất được. Vui lòng thử lại.");
  assert.ok(screen.getByText(account.full_name));

  logoutAvailable = true;
  await user().click(screen.getByRole("button", { name: "Đăng xuất" }));
  await screen.findByText("Đã đăng xuất.");
  reloaded.unmount();
  document.body.innerHTML = '<div id="root"></div>';
  renderUI(h(App));
  await screen.findByRole("heading", { name: "Đăng nhập" });
});

test("A temporary session check failure can be retried", async (t) => {
  let available = false;
  t.mock.method(globalThis, "fetch", async (url) => {
    if (url.endsWith("/auth/me"))
      return available ? Response.json(account) : Response.json({}, { status: 503 });
    return Response.json(page([]));
  });
  renderUI(h(App));
  await screen.findByText("Không kiểm tra được phiên đăng nhập.");
  assert.equal(screen.queryByRole("heading", { name: "Đăng nhập" }), null);
  available = true;
  await user().click(screen.getByRole("button", { name: "Thử lại" }));
  await screen.findByText(account.full_name);
});

test("Mobile menu supports navigation, closes after choosing a page and unlocks content", async () => {
  width = 390;
  renderUI(
    h(Workspace, {
      api: workspaceApi,
      user: account,
      logout: () => {},
      changePassword: () => {},
    }),
  );
  await waitFor(() =>
    assert.ok(
      screen.queryByText("Đang tải dữ liệu…") === null,
      "initial data should finish loading",
    ),
  );
  const opener = screen.getByRole("button", { name: "Mở menu điều hướng" });
  await user().click(opener);
  const drawer = screen.getByRole("dialog", { name: "Menu điều hướng" });
  assert.equal(opener.getAttribute("aria-expanded"), "true");
  await user().click(
    within(drawer).getByRole("button", { name: "Phòng họp", exact: true }),
  );
  assert.ok(screen.queryByRole("dialog") === null, "dialog should close");
  assert.ok(screen.getByRole("heading", { name: "Phòng họp", exact: true }));
  assert.equal(document.getElementById("root").inert, false);
  await user().click(
    screen.getByRole("button", { name: "Mở menu điều hướng" }),
  );
  fireEvent.keyDown(document, { key: "Escape" });
  assert.ok(screen.queryByRole("dialog") === null, "dialog should close");
});

test("The employee menu keeps privileged actions hidden on mobile", async () => {
  width = 390;
  renderUI(
    h(Workspace, {
      api: workspaceApi,
      user: { ...account, roles: ["EMPLOYEE"] },
      logout: () => {},
      changePassword: () => {},
    }),
  );
  await user().click(
    screen.getByRole("button", { name: "Mở menu điều hướng" }),
  );
  const nav = screen.getByRole("navigation", { name: "Điều hướng chính" });
  for (const name of ["Tài khoản", "Chờ tôi duyệt", "Báo cáo phòng"])
    assert.equal(
      within(nav).queryByRole("button", { name, exact: true }),
      null,
    );
  assert.ok(
    within(nav).getByRole("button", { name: "Tạo yêu cầu lịch", exact: true }),
  );
});

const report = {
  period_from: "2026-11-16T00:00:00+07:00",
  period_to: "2026-11-17T00:00:00+07:00",
  generated_at: "2026-11-15T01:00:00Z",
  basis: "PLANNED_BOOKINGS",
  rooms: [],
  total: {
    confirmed_count: 1,
    cancelled_count: 0,
    meeting_hours: 1,
    buffer_hours: 0.25,
    service_hours: 8,
    planned_rate_percent: 12.5,
  },
};
test("Selecting specific report rooms requires a choice and sends only selected IDs", async () => {
  const calls = [];
  renderUI(
    h(UsageReport, {
      api: async (path) => {
        calls.push(path);
        return report;
      },
      user: account,
      rooms: [room],
    }),
  );
  await user().click(screen.getByRole("radio", { name: "Chọn phòng cụ thể" }));
  await user().click(
    screen.getByRole("button", { name: "Xem báo cáo", exact: true }),
  );
  assert.equal(calls.length, 0);
  assert.match(screen.getByRole("alert").textContent, /ít nhất một phòng/);
  await user().click(screen.getByRole("checkbox", { name: /A101/ }));
  await user().click(
    screen.getByRole("button", { name: "Xem báo cáo", exact: true }),
  );
  await screen.findByRole("table");
  assert.equal(
    new URL("http://localhost" + calls[0]).searchParams.get("room_ids"),
    "room-a",
  );
});

test("Changing report dates clears stale results and reversed dates do not issue a request", async () => {
  let calls = 0;
  renderUI(
    h(UsageReport, {
      api: async () => {
        calls++;
        return report;
      },
      user: account,
      rooms: [room],
    }),
  );
  await user().click(
    screen.getByRole("button", { name: "Xem báo cáo", exact: true }),
  );
  await screen.findByRole("table");
  fireEvent.change(screen.getByLabelText("Từ ngày"), {
    target: { value: "2026-11-20" },
  });
  fireEvent.change(screen.getByLabelText("Đến ngày (không gồm ngày này)"), {
    target: { value: "2026-11-19" },
  });
  assert.ok(
    screen.queryByRole("table") === null,
    "stale table should be removed",
  );
  await user().click(
    screen.getByRole("button", { name: "Xem báo cáo", exact: true }),
  );
  assert.match(screen.getByRole("alert").textContent, /sau ngày bắt đầu/);
  assert.equal(calls, 1);
});
