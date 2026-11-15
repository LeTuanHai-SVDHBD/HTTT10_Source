import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const paths = {
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M16 3v4M8 3v4M3 11h18m-12 4h.01M12 15h.01M16 15h.01" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  inbox: (
    <>
      <path d="m4 4-2 9v7h20v-7l-2-9ZM2 13h6l2 3h4l2-3h6" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  building: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 7h1m6 0h1M8 11h1m6 0h1M8 15h1m6 0h1m-6 6v-3h4v3" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3 10 5-10 5L2 8Zm-9 9 9 5 9-5m-18 5 9 5 9-5" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 21v-3a6 6 0 0 1 12 0v3m2-17a3 3 0 0 1 0 6m4 11v-3a6 6 0 0 0-3-5" />
    </>
  ),
  chart: (
    <>
      <path d="M4 3v18h17M8 16v-4m5 4V7m5 9v-6" />
    </>
  ),
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  logout: (
    <>
      <path d="M9 4H4v16h5m5-12 4 4-4 4m-5-4h12" />
    </>
  ),
  key: (
    <>
      <circle cx="8" cy="9" r="5" />
      <path d="m12 13 8 8m-4-4 3-3m-6 0 3-3" />
    </>
  ),
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  shield: (
    <>
      <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  eyeOff: (
    <>
      <path d="m3 3 18 18M10 5h2c7 0 10 7 10 7a19 19 0 0 1-4 5M6 6a18 18 0 0 0-4 6s3 7 10 7a12 12 0 0 0 4-1M10 10a3 3 0 0 0 4 4" />
    </>
  ),
};
export function Icon({ name, size = 20, ...props }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {paths[name] || paths.calendar}
    </svg>
  );
}

export function useSmallScreen() {
  const query = "(max-width: 1023px)";
  const [small, setSmall] = useState(
    () => window.matchMedia?.(query).matches || false,
  );
  useEffect(() => {
    const media = window.matchMedia?.(query);
    if (!media) return;
    const update = () => setSmall(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return small;
}

let dialogStack = [];
let restorePage = null;

// Dialogs render above the app so focus and scrolling stay in the active surface.
export function Dialog({
  children,
  onClose,
  busy = false,
  labelledBy,
  label,
  drawer = false,
}) {
  const panel = useRef(null),
    close = useRef(onClose),
    blocked = useRef(busy);
  close.current = onClose;
  blocked.current = busy;
  useEffect(() => {
    const previous = document.activeElement;
    const root = document.getElementById("root");
    const node = panel.current;
    if (!dialogStack.length) {
      restorePage = {
        overflow: document.body.style.overflow,
        inert: root?.inert || false,
      };
      document.body.style.overflow = "hidden";
      if (root) root.inert = true;
    }
    dialogStack.push(node);
    node?.focus({ preventScroll: true });
    const onKey = (event) => {
      if (dialogStack.at(-1) !== node) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        if (!blocked.current) close.current?.();
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        panel.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex="0"]',
        ) || [],
      ).filter(
        (node) =>
          !node.matches(":disabled") &&
          !node.hidden &&
          getComputedStyle(node).display !== "none" &&
          getComputedStyle(node).visibility !== "hidden",
      );
      const first = focusable[0],
        last = focusable.at(-1);
      if (!first) {
        event.preventDefault();
        panel.current?.focus();
        return;
      }
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === panel.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          document.activeElement === panel.current)
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      const wasTop = dialogStack.at(-1) === node;
      dialogStack = dialogStack.filter((entry) => entry !== node);
      if (!dialogStack.length && restorePage) {
        document.body.style.overflow = restorePage.overflow;
        if (root) root.inert = restorePage.inert;
        restorePage = null;
      }
      if (wasTop) {
        const next = dialogStack.at(-1);
        if (previous?.isConnected && (!next || next.contains(previous)))
          previous.focus({ preventScroll: true });
        else next?.focus({ preventScroll: true });
      }
    };
  }, []);
  return createPortal(
    <div className={"modal-backdrop" + (drawer ? " drawer-backdrop" : "")}>
      <section
        ref={panel}
        className={drawer ? "navigation-drawer" : "modal"}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-label={label}
        tabIndex={-1}
      >
        {children}
      </section>
    </div>,
    document.body,
  );
}

export function PasswordField({ label, id, disabled, ...props }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="password-group">
      <label htmlFor={id}>{label}</label>
      <div className="password-field">
        <input
          id={id}
          type={visible ? "text" : "password"}
          disabled={disabled}
          {...props}
        />
        <button
          type="button"
          className="password-toggle"
          disabled={disabled}
          aria-label={
            (visible ? "Ẩn " : "Hiện ") + label.toLocaleLowerCase("vi")
          }
          aria-pressed={visible}
          onClick={() => setVisible((value) => !value)}
        >
          <Icon name={visible ? "eyeOff" : "eye"} />
        </button>
      </div>
    </div>
  );
}
