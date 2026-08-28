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
  category: string | null;
  priority: string | null;
  needs_reply: boolean | null;
  classification_confidence: number | null;
  classification_model_version: string | null;
  classified_at: string | null;
};

export type EmailSearchResult = {
  email: Email;
  keyword_rank: number | null;
  vector_rank: number | null;
  keyword_score: number;
  vector_score: number;
  rrf_score: number;
  match_reason: string;
};

export type EmailSearchResponse = {
  query: string;
  results: EmailSearchResult[];
};
export type ClassificationBatch = {
  classified_count: number;
  by_category: Record<string, number>;
  by_priority: Record<string, number>;
  needs_reply_count: number;
  stage_counts: Record<string, number>;
};

export type ClassificationSummary = {
  total_classified: number;
  total_unclassified: number;
  by_category: Record<string, number>;
  by_priority: Record<string, number>;
  needs_reply_count: number;
};


export type CleanupSuggestion = {
  suggestion_type: string;
  title: string;
  description: string;
  email_count: number;
  estimated_time_saved_minutes: number;
  confidence: number;
};

export type InboxHealth = {
  score: number;
  total_emails: number;
  unread_count: number;
  high_priority_unread_count: number;
  pending_reply_count: number;
  cleanup_candidate_count: number;
  formula: string;
  suggestions: CleanupSuggestion[];
};
export type Thread = {
  id: number;
  gmail_thread_id: string;
  subject: string | null;
  snippet: string | null;
  last_message_at: string | null;
  summary: string | null;
  summary_model_version: string | null;
  summarized_at: string | null;
};

export type SyncJob = {
  id: number;
  user_id: number;
  gmail_account_id: number;
  job_type: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  synced_count: number;
  created_count: number;
  updated_count: number;
  celery_task_id: string | null;
  error_type: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
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

export async function searchEmails(query: string) {
  return request<EmailSearchResponse>(`/gmail/search?q=${encodeURIComponent(query)}&limit=8`);
}
export async function queueGmailSync(accountId?: number) {
  const suffix = accountId ? `?account_id=${accountId}` : "";
  return request<SyncJob>(`/gmail/sync${suffix}`, { method: "POST" });
}

export async function getSyncJobs() {
  return request<SyncJob[]>("/gmail/sync/jobs");
}

export async function classifyEmails() {
  return request<ClassificationBatch>("/gmail/classify", { method: "POST" });
}

export async function getClassificationSummary() {
  return request<ClassificationSummary>("/gmail/classification/summary");
}
export async function getInboxInsights() {
  return request<InboxHealth>("/gmail/insights");
}

export async function getThreads() {
  return request<Thread[]>("/gmail/threads?limit=10");
}


