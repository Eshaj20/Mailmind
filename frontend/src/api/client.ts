const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "mailmind_token";

export type SignupPayload = {
  email: string;
  password: string;
  full_name?: string;
};

export type User = {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
};

export type GmailAccount = {
  id: number;
  google_email: string;
  history_id: string | null;
  sync_status: string;
  last_synced_at: string | null;
};

export type Email = {
  id: number;
  gmail_message_id: string;
  sender: string | null;
  recipients: string | null;
  subject: string | null;
  snippet: string | null;
  labels: string[] | null;
  is_read: boolean;
  received_at: string | null;
};

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);

  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail ?? "Request failed");
  }

  return response.json() as Promise<T>;
}

export async function signup(payload: SignupPayload) {
  return request<User>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(email: string, password: string) {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);

  const token = await request<{ access_token: string; token_type: string }>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  setToken(token.access_token);
  return token;
}

export async function getMe() {
  return request<User>("/auth/me");
}

export async function getGmailOAuthUrl() {
  return request<{ authorization_url: string }>("/gmail/oauth/authorize");
}

export async function getGmailAccounts() {
  return request<GmailAccount[]>("/gmail/accounts");
}

export async function getEmails() {
  return request<Email[]>("/gmail/emails?limit=5");
}
