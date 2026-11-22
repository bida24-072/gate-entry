import { API_BASE } from "./config.js";

const KEY = "gate_session";

export function getSession() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY));
  } catch {
    return null;
  }
}
export function setSession(s) {
  sessionStorage.setItem(KEY, JSON.stringify(s));
}
export function clearSession() {
  sessionStorage.removeItem(KEY);
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function detailOf(data) {
  if (!data) return "";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join("; ");
  return "";
}

export async function api(path, { method = "GET", body } = {}) {
  const session = getSession();
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (session && session.token) headers["Authorization"] = `Bearer ${session.token}`;

  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection and the API address.");
  }

  if (res.status === 401 && session) {
    clearSession();
    location.hash = "#/login";
    throw new ApiError(401, "Session expired. Please sign in again.");
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) throw new ApiError(res.status, detailOf(data) || `Request failed (${res.status})`);
  return data;
}
