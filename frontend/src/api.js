export function client(token, onExpired) {
  return async (path, method = "GET", body) => {
    const response = await fetch("/api/v1" + path, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const data =
      response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && token) onExpired();
      const fields = data?.error?.field_errors
        ?.map((f) => f.path.replace(/^body\./, ""))
        .join(", ");
      throw new Error(
        (data?.error?.message ||
          "Không kết nối được dịch vụ. Vui lòng thử lại.") +
          (fields ? " Kiểm tra: " + fields + "." : ""),
      );
    }
    return data;
  };
}

// Selectors follow pagination instead of silently dropping records after 100.
export async function allPages(api, path) {
  let items = [],
    page = 1,
    result;
  do {
    result = await api(
      `${path}${path.includes("?") ? "&" : "?"}page=${page++}&page_size=100`,
    );
    items.push(...result.items);
  } while (items.length < result.total && result.items.length);
  return items;
}
export const roles = {
  EMPLOYEE: "Nhân viên",
  APPROVER: "Người phê duyệt",
  ADMIN: "Quản trị viên",
};
export const localInput = (value = new Date()) => {
  const d = new Date(value);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
export const stamp = (value) =>
  new Date(value).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    dateStyle: "short",
    timeStyle: "short",
  });
