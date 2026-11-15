import React, { useEffect, useId, useState } from "react";
import { allPages, stamp } from "./api";

export function Documents({ api, scheduleId, revisionId, canUpload = false }) {
  const id = useId();
  const [items, setItems] = useState([]);
  const [hidden, setHidden] = useState(false);
  const [allContexts, setAllContexts] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [target, setTarget] = useState("");
  const [hideTarget, setHideTarget] = useState(null);
  const [reason, setReason] = useState("");
  const [inputKey, setInputKey] = useState(0);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    allPages(
      api,
      `/schedules/${scheduleId}/documents?include_hidden=${hidden}${allContexts ? "" : `&context_revision_id=${revisionId}`}`,
    )
      .then((value) => {
        if (alive) {
          setItems(value);
          setUncertain(false);
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // api is recreated by the parent; IDs and refresh define the read context.
  }, [scheduleId, revisionId, hidden, allContexts, refresh]);

  async function command(action, success) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setFile(null);
      setName("");
      setTarget("");
      setHideTarget(null);
      setReason("");
      setInputKey((v) => v + 1);
      setNotice(success);
      setRefresh((v) => v + 1);
    } catch (e) {
      setError(e.message);
      if (!e.status || e.status >= 500) {
        setUncertain(true);
        setNotice(
          "Chưa xác định thao tác đã được lưu hay chưa. Tải lại danh sách và đối chiếu trước khi gửi lại.",
        );
      } else if (e.code === "DOCUMENT_VERSION_CHANGED") {
        setUncertain(true);
        setNotice(
          "Tài liệu đã thay đổi. Tải lại danh sách trước khi thao tác tiếp.",
        );
      }
    } finally {
      setBusy(false);
    }
  }
  function upload(e) {
    e.preventDefault();
    if (!file) return;
    if (!file.size || file.size > 20 * 1024 * 1024) {
      setError("Tệp phải có dung lượng từ 1 byte đến 20 MiB.");
      return;
    }
    const doc = items.find((v) => v.id === target);
    if (target && !doc) return;
    const body = new FormData();
    body.append(
      "metadata",
      JSON.stringify({
        context_revision_id: revisionId,
        ...(doc
          ? { expected_latest_version_id: doc.versions.at(-1).id }
          : { display_name: name.trim() }),
      }),
    );
    body.append("file", file);
    command(
      () =>
        api(
          doc
            ? `/documents/${doc.id}/versions`
            : `/schedules/${scheduleId}/documents`,
          "POST",
          body,
        ),
      "Đã lưu tài liệu.",
    );
  }
  async function download(doc, version) {
    setBusy(true);
    setError("");
    try {
      const blob = await api(
        `/documents/${doc.id}/versions/${version.id}/content`,
        "GET",
        undefined,
        { blob: true },
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = version.original_filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const disabled = busy || loading || uncertain;
  return (
    <section className="documents" aria-labelledby={id + "-title"}>
      <h4 id={id + "-title"}>Tài liệu họp</h4>
      <p className="muted">
        Mỗi phiên bản tệp giữ quyền xem theo bản lịch đính kèm. Tệp cũ không tự
        chuyển sang bản lịch mới.
      </p>
      <div className="document-options">
        <label>
          <input
            type="checkbox"
            checked={hidden}
            disabled={busy}
            onChange={(e) => setHidden(e.target.checked)}
          />{" "}
          Hiện tài liệu đã ẩn
        </label>
        <label>
          <input
            type="checkbox"
            checked={allContexts}
            disabled={busy}
            onChange={(e) => setAllContexts(e.target.checked)}
          />{" "}
          Xem tài liệu các bản lịch được phép
        </label>
        <button
          type="button"
          className="secondary compact"
          disabled={busy || loading}
          onClick={() => {
            setError("");
            setRefresh((v) => v + 1);
          }}
        >
          Tải lại tài liệu
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="info-line" role="status">
          {notice}
        </p>
      )}
      {loading ? (
        <p>Đang tải tài liệu…</p>
      ) : (
        items.length === 0 && <p>Chưa có tài liệu trong phạm vi đang xem.</p>
      )}
      {items.map((doc) => (
        <article className="document-card" key={doc.id}>
          <b>{doc.display_name}</b>{" "}
          {doc.is_hidden && <span className="tag">Đã ẩn</span>}
          <ul>
            {doc.versions.map((v) => (
              <li key={v.id}>
                <span>
                  v{v.version_no} · {v.original_filename} ·{" "}
                  {(v.size_bytes / 1024).toFixed(1)} KiB
                  <br />
                  <small>
                    {v.uploaded_by.full_name} · {stamp(v.created_at)}
                  </small>
                </span>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={busy}
                  onClick={() => download(doc, v)}
                >
                  Tải xuống v{v.version_no}
                </button>
              </li>
            ))}
          </ul>
          {canUpload && doc.allowed_actions.includes("HIDE") && (
            <button
              type="button"
              className="secondary compact"
              disabled={disabled}
              onClick={() => {
                setHideTarget(doc);
                setReason("");
              }}
            >
              Ẩn tài liệu
            </button>
          )}
        </article>
      ))}
      {canUpload && (
        <form className="document-form" onSubmit={upload}>
          <h5>Thêm tệp vào bản lịch đang xem</h5>
          <label htmlFor={id + "-target"}>Lưu vào tài liệu</label>
          <select
            id={id + "-target"}
            value={target}
            disabled={disabled}
            onChange={(e) => setTarget(e.target.value)}
          >
            <option value="">Tạo tài liệu mới</option>
            {items
              .filter((d) => d.allowed_actions.includes("UPLOAD_VERSION"))
              .map((d) => (
                <option key={d.id} value={d.id}>
                  Phiên bản mới: {d.display_name}
                </option>
              ))}
          </select>
          {!target && (
            <>
              <label htmlFor={id + "-name"}>Tên tài liệu</label>
              <input
                id={id + "-name"}
                value={name}
                disabled={disabled}
                required
                maxLength={255}
                onChange={(e) => setName(e.target.value)}
              />
            </>
          )}
          <label htmlFor={id + "-file"}>Tệp đính kèm</label>
          <input
            key={inputKey}
            id={id + "-file"}
            type="file"
            accept=".pdf,.docx,.pptx,.xlsx,.jpg,.jpeg,.png"
            disabled={disabled}
            required
            onChange={(e) => setFile(e.target.files[0] || null)}
          />
          <small>
            PDF, DOCX, PPTX, XLSX, JPG, JPEG, PNG · tối đa 20 MiB/tệp.
          </small>
          <button disabled={disabled || !file || (!target && !name.trim())}>
            Lưu tài liệu
          </button>
        </form>
      )}
      {hideTarget && (
        <form
          className="document-form"
          onSubmit={(e) => {
            e.preventDefault();
            command(
              () =>
                api(`/documents/${hideTarget.id}/hides`, "POST", {
                  expected_latest_version_id: hideTarget.versions.at(-1).id,
                  reason: reason.trim(),
                }),
              "Đã ẩn tài liệu; lịch sử vẫn được giữ.",
            );
          }}
        >
          <label htmlFor={id + "-reason"}>
            Lý do ẩn {hideTarget.display_name}
          </label>
          <input
            id={id + "-reason"}
            required
            maxLength={500}
            disabled={disabled}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button disabled={disabled || !reason.trim()}>
            Xác nhận ẩn tài liệu
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => setHideTarget(null)}
          >
            Thôi ẩn
          </button>
        </form>
      )}
    </section>
  );
}
