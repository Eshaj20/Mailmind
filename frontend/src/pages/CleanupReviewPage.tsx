import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Archive, Check, Inbox, RotateCcw, Search, X } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import {
  applyCleanupAction,
  clearToken,
  getCleanupPreview,
  getGmailAccounts,
  getMe,
  getToken,
  submitEmailFeedback,
  undoCleanupAction,
  type CleanupAction,
  type CleanupPreviewItem,
} from "../api/client";

type ReviewFilter = "all" | "spam_risk" | "promotions" | "updates" | "low_priority" | "unread";

const filterLabels: Record<ReviewFilter, string> = {
  all: "All candidates",
  spam_risk: "Spam risk",
  promotions: "Promotions",
  updates: "Updates",
  low_priority: "Low priority",
  unread: "Unread",
};

function matchesFilter(item: CleanupPreviewItem, filter: ReviewFilter) {
  const email = item.email;
  if (filter === "all") return true;
  if (filter === "spam_risk") return (email.spam_score ?? 0) >= 0.7 || email.spam_label === "spam";
  if (filter === "promotions") return email.category === "promotions";
  if (filter === "updates") return email.category === "updates";
  if (filter === "low_priority") return email.priority === "low";
  if (filter === "unread") return !email.is_read;
  return true;
}

function formatDate(value: string | null) {
  if (!value) return "Unknown date";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export function CleanupReviewPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const hasToken = Boolean(getToken());
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [lastActionIds, setLastActionIds] = useState<number[]>([]);

  const meQuery = useQuery({ queryKey: ["me"], queryFn: getMe, enabled: hasToken, retry: false });
  const accountsQuery = useQuery({ queryKey: ["gmail-accounts"], queryFn: getGmailAccounts, enabled: hasToken, retry: false });
  const cleanupPreviewQuery = useQuery({
    queryKey: ["cleanup-preview", "review"],
    queryFn: () => getCleanupPreview(100),
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });

  const items = cleanupPreviewQuery.data?.items ?? [];
  const visibleItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((item) => {
      if (!matchesFilter(item, filter)) return false;
      if (!normalizedQuery) return true;
      const haystack = [item.email.subject, item.email.sender, item.email.snippet, item.reason]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [filter, items, query]);

  const selectedVisibleIds = selectedIds.filter((id) => visibleItems.some((item) => item.email.id === id));
  const allVisibleSelected = visibleItems.length > 0 && selectedVisibleIds.length === visibleItems.length;

  const cleanupMutation = useMutation({
    mutationFn: (action: CleanupAction) => applyCleanupAction(selectedVisibleIds, action),
    onSuccess: (data) => {
      setLastActionIds(data.action_ids);
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
      queryClient.invalidateQueries({ queryKey: ["sender-insights"] });
    },
  });

  const undoMutation = useMutation({
    mutationFn: async () => Promise.all(lastActionIds.map((actionId) => undoCleanupAction(actionId))),
    onSuccess: () => {
      setLastActionIds([]);
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
      queryClient.invalidateQueries({ queryKey: ["sender-insights"] });
    },
  });

  const feedbackMutation = useMutation({
    mutationFn: (emailId: number) =>
      submitEmailFeedback({
        email_id: emailId,
        feedback_type: "not_cleanup",
        corrected_category: "primary",
        corrected_priority: "medium",
        corrected_needs_reply: null,
        note: "User removed this email from cleanup review.",
      }),
    onSuccess: (_, emailId) => {
      setSelectedIds((current) => current.filter((id) => id !== emailId));
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
    },
  });

  if (!hasToken) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <section className="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-8 shadow-panel">
          <Inbox className="text-moss" size={30} aria-hidden />
          <h1 className="mt-5 text-2xl font-semibold text-ink">Login required</h1>
          <p className="mt-2 text-sm text-slate-600">Open your MailMind workspace before reviewing cleanup candidates.</p>
          <Link className="mt-6 inline-flex rounded-lg bg-ink px-4 py-2.5 font-semibold text-white hover:bg-moss" to="/auth">
            Continue
          </Link>
        </section>
      </main>
    );
  }

  const connectedAccount = accountsQuery.data?.[0];
  const selectedCount = selectedVisibleIds.length;

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100"
              to="/"
              title="Back to dashboard"
            >
              <ArrowLeft size={18} aria-hidden />
            </Link>
            <div>
              <p className="text-sm font-medium text-moss">MailMind cleanup</p>
              <h1 className="text-2xl font-semibold text-ink">Review unwanted emails</h1>
            </div>
          </div>
          <button
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            type="button"
            onClick={() => {
              clearToken();
              navigate("/auth");
            }}
          >
            Logout
          </button>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-8">
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Workspace</p>
            <p className="mt-1 truncate font-semibold text-ink">{meQuery.data?.email ?? "Loading..."}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Gmail account</p>
            <p className="mt-1 truncate font-semibold text-ink">{connectedAccount?.google_email ?? "Not connected"}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Cleanup candidates</p>
            <p className="mt-1 text-2xl font-semibold text-ink">{cleanupPreviewQuery.data?.total_candidates ?? 0}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Estimated time saved</p>
            <p className="mt-1 text-2xl font-semibold text-ink">{cleanupPreviewQuery.data?.estimated_time_saved_minutes ?? 0} min</p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-8">
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              {(Object.keys(filterLabels) as ReviewFilter[]).map((key) => (
                <button
                  key={key}
                  className={`rounded-lg px-3 py-2 text-sm font-semibold ${filter === key ? "bg-ink text-white" : "border border-slate-200 text-slate-700 hover:bg-slate-50"}`}
                  type="button"
                  onClick={() => {
                    setFilter(key);
                    setSelectedIds([]);
                  }}
                >
                  {filterLabels[key]}
                </button>
              ))}
            </div>
            <div className="relative w-full lg:max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} aria-hidden />
              <input
                className="w-full rounded-lg border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-moss"
                placeholder="Search sender, subject, reason"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
          </div>

          <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <button
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
                disabled={visibleItems.length === 0}
                onClick={() => setSelectedIds(allVisibleSelected ? [] : visibleItems.map((item) => item.email.id))}
              >
                <Check size={16} aria-hidden />
                {allVisibleSelected ? "Clear selection" : "Select visible"}
              </button>
              <span className="text-sm text-slate-500">{selectedCount} selected from {visibleItems.length} visible</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-ink px-3 py-2 text-sm font-semibold text-white hover:bg-moss disabled:opacity-60"
                type="button"
                disabled={selectedCount === 0 || cleanupMutation.isPending}
                onClick={() => cleanupMutation.mutate("archive")}
              >
                <Archive size={16} aria-hidden />
                Archive selected
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                type="button"
                disabled={selectedCount === 0 || cleanupMutation.isPending}
                onClick={() => cleanupMutation.mutate("mark_read")}
              >
                <Check size={16} aria-hidden />
                Mark read
              </button>
            </div>
          </div>

          {(cleanupMutation.isError || undoMutation.isError || feedbackMutation.isError) && (
            <p className="mt-4 rounded-lg bg-coral/10 px-4 py-3 text-sm text-coral">
              {cleanupMutation.error?.message ?? undoMutation.error?.message ?? feedbackMutation.error?.message}
            </p>
          )}

          {lastActionIds.length > 0 && (
            <div className="mt-4 flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm font-medium text-ink">Last cleanup changed {lastActionIds.length} email{lastActionIds.length === 1 ? "" : "s"}.</p>
              <button
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink px-3 py-2 text-sm font-semibold text-white hover:bg-moss disabled:opacity-60"
                type="button"
                disabled={undoMutation.isPending}
                onClick={() => undoMutation.mutate()}
              >
                <RotateCcw size={16} aria-hidden />
                {undoMutation.isPending ? "Undoing..." : "Undo last cleanup"}
              </button>
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-10">
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          {cleanupPreviewQuery.isLoading && <p className="p-6 text-sm text-slate-500">Loading cleanup candidates...</p>}
          {!cleanupPreviewQuery.isLoading && !connectedAccount && (
            <p className="p-6 text-sm text-slate-500">Connect Gmail or seed demo inbox data to review cleanup candidates.</p>
          )}
          {!cleanupPreviewQuery.isLoading && connectedAccount && visibleItems.length === 0 && (
            <p className="p-6 text-sm text-slate-500">No cleanup candidates match this view.</p>
          )}
          {visibleItems.map((item) => {
            const selected = selectedIds.includes(item.email.id);
            return (
              <article key={item.email.id} className={`border-b border-slate-100 p-4 last:border-b-0 ${selected ? "bg-moss/5" : "bg-white"}`}>
                <div className="flex gap-4">
                  <input
                    className="mt-1 h-4 w-4 accent-moss"
                    type="checkbox"
                    checked={selected}
                    onChange={(event) => {
                      setSelectedIds((current) =>
                        event.target.checked ? [...current, item.email.id] : current.filter((id) => id !== item.email.id),
                      );
                    }}
                    aria-label={`Select ${item.email.subject ?? "email"}`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-ink">{item.email.subject ?? "No subject"}</p>
                        <p className="mt-1 truncate text-sm text-slate-500">{item.email.sender ?? "Unknown sender"}</p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <span className="rounded-full bg-moss/10 px-2.5 py-1 text-xs font-medium text-moss">{item.email.category ?? "uncategorized"}</span>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">{item.email.priority ?? "priority n/a"}</span>
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700">{Math.round(item.confidence * 100)}%</span>
                        {item.email.spam_score !== null && item.email.spam_score >= 0.7 && (
                          <span className="rounded-full bg-coral/10 px-2.5 py-1 text-xs font-medium text-coral">
                            Spam risk {Math.round(item.email.spam_score * 100)}%
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm text-slate-600">{item.email.snippet}</p>
                    <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="text-xs text-slate-500">
                        <span>{formatDate(item.email.received_at)}</span>
                        <span className="mx-2">|</span>
                        <span>{item.reason}</span>
                      </div>
                      <button
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-50 disabled:opacity-60"
                        type="button"
                        disabled={feedbackMutation.isPending}
                        onClick={() => feedbackMutation.mutate(item.email.id)}
                      >
                        <X size={14} aria-hidden />
                        Not cleanup
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}