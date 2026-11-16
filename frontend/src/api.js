// Thin wrapper around fetch(): adds the JWT, refreshes it once when it has
// expired, and turns error responses into ApiError exceptions.

const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

const ACCESS_KEY = "sas.access";
const REFRESH_KEY = "sas.refresh";
const USER_KEY = "sas.user";

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  get user() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch {
      return null;
    }
  },
  setTokens(access, refresh) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  setUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

export class ApiError extends Error {
  constructor(status, data) {
    super(errorMessage({ status, data }));
    this.status = status;
    this.data = data;
    this.code = data && data.code;
  }
}

// Turns DRF error payloads ({detail} or {field: [messages]}) into one string.
export function errorMessage(err) {
  const data = err && err.data;
  if (data) {
    if (typeof data === "string") return data;
    if (data.detail) return String(data.detail);
    const parts = [];
    for (const [field, value] of Object.entries(data)) {
      const text = Array.isArray(value) ? value.join(" ") : String(value);
      parts.push(field === "non_field_errors" ? text : `${field}: ${text}`);
    }
    if (parts.length) return parts.join(" ");
  }
  if (err && err.status === 429) return "Too many requests. Please wait a moment and try again.";
  if (err && err.message && err.message !== "undefined") return err.message;
  return "Something went wrong. Please try again.";
}

let refreshPromise = null;

function refreshAccess() {
  if (refreshPromise) return refreshPromise;
  const refresh = tokenStore.refresh;
  if (!refresh) return Promise.resolve(null);
  refreshPromise = fetch(`${API_BASE}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  })
    .then(async (res) => {
      if (!res.ok) return null;
      const data = await res.json();
      tokenStore.setTokens(data.access, data.refresh);
      return data.access;
    })
    .catch(() => null)
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

export async function request(path, { method = "GET", body, auth = true, blob = false } = {}) {
  const send = (token) =>
    fetch(`${API_BASE}/api${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

  let response;
  try {
    response = await send(tokenStore.access);
  } catch {
    throw new ApiError(0, { detail: "Cannot reach the server. Check your connection." });
  }

  if (response.status === 401 && auth) {
    const fresh = await refreshAccess();
    if (fresh) {
      response = await send(fresh);
    } else {
      tokenStore.clear();
      window.dispatchEvent(new Event("sas:logout"));
    }
  }

  if (blob) {
    if (!response.ok) throw new ApiError(response.status, null);
    return response.blob();
  }
  if (response.status === 204) return null;

  let data = null;
  try {
    data = await response.json();
  } catch {
    /* empty body */
  }
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

export const api = {
  get: (path) => request(path),
  post: (path, body = {}) => request(path, { method: "POST", body }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  del: (path) => request(path, { method: "DELETE" }),
  download: (path) => request(path, { blob: true }),
};
