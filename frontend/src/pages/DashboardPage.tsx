import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain, LogOut, Mail, RefreshCw, Search, ShieldCheck, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import {
  classifyEmails,
  clearToken,
  getClassificationSummary,
  getEmails,
  getGmailAccounts,
  getGmailOAuthUrl,
  getMe,
  getSyncJobs,
  getThreads,
  getToken,
  queueGmailSync,
  searchEmails,
} from "../api/client";

const milestones = [
  { label: "Gmail sync", value: "Week 2", icon: Mail },
  { label: "Sync engine", value: "Week 3", icon: RefreshCw },
  { label: "AI classification", value: "Week 4", icon: Brain },
  { label: "Hybrid search", value: "Week 5", icon: Search },
  { label: "Inbox intelligence", value: "Week 6", icon: Sparkles },
];

const CATEGORY_LABELS: Record<string, string> = {
  primary: "Primary",
  promotions: "Promotions",
  social: "Social",
  updates: "Updates",
  spam: "Spam",
};

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-coral/10 text-coral",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-100 text-slate-500",
};

export function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const hasToken = Boolean(getToken());
  const [searchQuery, setSearchQuery] = useState("");
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: hasToken,
    retry: false,
  });
  const accountsQuery = useQuery({
    queryKey: ["gmail-accounts"],
    queryFn: getGmailAccounts,
    enabled: hasToken,
    retry: false,
  });
  const emailsQuery = useQuery({
    queryKey: ["emails"],
    queryFn: getEmails,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });
  const syncJobsQuery = useQuery({
    queryKey: ["sync-jobs"],
    queryFn: getSyncJobs,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
    refetchInterval: 5000,
  });
  const classificationSummaryQuery = useQuery({
    queryKey: ["classification-summary"],
    queryFn: getClassificationSummary,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });
  const searchResultsQuery = useQuery({
    queryKey: ["email-search", searchQuery],
    queryFn: () => searchEmails(searchQuery),
    enabled: hasToken && Boolean(accountsQuery.data?.length) && searchQuery.trim().length >= 2,
    retry: false,
  });
  const threadsQuery = useQuery({
    queryKey: ["threads"],
    queryFn: getThreads,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });
  const connectMutation = useMutation({
    mutationFn: getGmailOAuthUrl,
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
  });
  const syncMutation = useMutation({
    mutationFn: (accountId: number | undefined) => queueGmailSync(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["emails"] });
    },
  });
  const classifyMutation = useMutation({
    mutationFn: classifyEmails,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["classification-summary"] });
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
    },
  });

  if (!hasToken) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-mint px-6">
        <section className="w-full max-w-xl rounded-lg bg-white p-8 shadow-panel">
          <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-lg bg-ink text-white">
            <ShieldCheck size={24} aria-hidden />
          </div>
          <h1 className="text-3xl font-semibold text-ink">MailMind needs a workspace.</h1>
          <p className="mt-3 text-slate-600">
            Create an account or login to begin the Gmail integration milestone.
          </p>
          <Link
            className="mt-7 inline-flex rounded-lg bg-ink px-5 py-3 font-semibold text-white hover:bg-moss"
            to="/auth"
          >
            Continue
          </Link>
        </section>
      </main>
    );
  }

  const connectedAccount = accountsQuery.data?.[0];
  const latestJob = syncJobsQuery.data?.[0];
  const summary = classificationSummaryQuery.data;
  const hasUnclassified = Boolean(summary && summary.total_unclassified > 0);

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-medium text-moss">MailMind</p>
            <h1 className="text-2xl font-semibold text-ink">
              {meQuery.data?.full_name ?? meQuery.data?.email ?? "Inbox workspace"}
            </h1>
          </div>
          <button
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100"
            type="button"
            title="Logout"
            onClick={() => {
              clearToken();
              navigate("/auth");
            }}
          >
            <LogOut size={18} aria-hidden />
          </button>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-ink">Week 4 AI layer</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {milestones.map((item) => (
              <div key={item.label} className="rounded-lg border border-slate-200 p-4">
                <item.icon className="text-moss" size={22} aria-hidden />
                <p className="mt-3 font-semibold text-ink">{item.label}</p>
                <p className="text-sm text-slate-500">{item.value}</p>
              </div>
            ))}
          </div>
        </div>

        <aside className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-ink">
            {connectedAccount ? "Gmail connected" : "Connect Gmail"}
          </h2>
          <p className="mt-3 text-slate-600">
            {connectedAccount
              ? `${connectedAccount.google_email} is ready for background re-sync jobs.`
              : "Start Google OAuth, store the refresh token securely, and persist the first Gmail sync."}
          </p>
          {(connectMutation.isError || syncMutation.isError || classifyMutation.isError) && (
            <p className="mt-4 rounded-lg bg-coral/10 px-4 py-3 text-sm text-coral">
              {connectMutation.error?.message ?? syncMutation.error?.message ?? classifyMutation.error?.message}
            </p>
          )}
          <div className="mt-6 grid gap-3">
            <button
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-4 py-3 font-semibold text-white hover:bg-moss disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              disabled={connectMutation.isPending}
              onClick={() => connectMutation.mutate()}
            >
              <Mail size={18} aria-hidden />
              {connectedAccount ? "Reconnect Gmail" : connectMutation.isPending ? "Opening Google..." : "Connect Gmail"}
            </button>
            {connectedAccount && (
              <button
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-3 font-semibold text-ink hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                disabled={syncMutation.isPending}
                onClick={() => syncMutation.mutate(connectedAccount.id)}
              >
                <RefreshCw size={18} aria-hidden />
                {syncMutation.isPending ? "Queueing sync..." : "Queue sync"}
              </button>
            )}
            {connectedAccount && (
              <button
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-3 font-semibold text-ink hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                disabled={classifyMutation.isPending}
                onClick={() => classifyMutation.mutate()}
              >
                <Brain size={18} aria-hidden />
                {classifyMutation.isPending
                  ? "Classifying..."
                  : hasUnclassified
                    ? `Classify ${summary?.total_unclassified} email${summary?.total_unclassified === 1 ? "" : "s"}`
                    : "Run AI classification"}
              </button>
            )}
          </div>
          {latestJob && (
            <div className="mt-5 rounded-lg border border-slate-200 p-4 text-sm">
              <p className="font-semibold text-ink">Latest sync: {latestJob.status}</p>
              <p className="mt-1 text-slate-500">
                {latestJob.created_count} created, {latestJob.updated_count} updated, attempt {latestJob.attempt_count}
                /{latestJob.max_attempts}
              </p>
            </div>
          )}
        </aside>
      </section>

      {connectedAccount && summary && summary.total_classified > 0 && (
        <section className="mx-auto max-w-6xl px-6 pb-8">
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-ink">Inbox intelligence</h2>
              <p className="text-sm text-slate-500">
                {summary.total_classified} classified
                {summary.total_unclassified > 0 ? `, ${summary.total_unclassified} pending` : ""}
              </p>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <div key={key} className="rounded-lg border border-slate-200 p-4 text-center">
                  <p className="text-2xl font-semibold text-ink">{summary.by_category[key] ?? 0}</p>
                  <p className="mt-1 text-sm text-slate-500">{label}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-600">
              <span className="rounded-full bg-slate-100 px-3 py-1">
                {summary.by_priority.high ?? 0} high priority
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1">
                {summary.by_priority.medium ?? 0} medium priority
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1">
                {summary.needs_reply_count} need a reply
              </span>
            </div>
          </div>
        </section>
      )}

      {connectedAccount && (
        <section className="mx-auto max-w-6xl px-6 pb-8">
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-ink">Hybrid search</h2>
                <p className="mt-1 text-sm text-slate-500">Keyword + semantic ranking merged with RRF.</p>
              </div>
              <div className="relative w-full sm:max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} aria-hidden />
                <input
                  className="w-full rounded-lg border border-slate-200 py-3 pl-10 pr-3 text-sm outline-none focus:border-moss"
                  placeholder="Search interview, bill, travel..."
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
              </div>
            </div>
            {searchQuery.trim().length >= 2 && (
              <div className="mt-5 divide-y divide-slate-100">
                {(searchResultsQuery.data?.results ?? []).map((result) => (
                  <div key={result.email.id} className="py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-semibold text-ink">{result.email.subject ?? "No subject"}</p>
                        <p className="mt-1 text-sm text-slate-500">{result.email.sender ?? "Unknown sender"}</p>
                      </div>
                      <span className="shrink-0 rounded-full bg-moss/10 px-2.5 py-1 text-xs font-medium text-moss">
                        {result.match_reason.replace(/_/g, " ")}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{result.email.snippet}</p>
                    <p className="mt-2 text-xs text-slate-400">
                      RRF {result.rrf_score.toFixed(4)} - keyword #{result.keyword_rank ?? "-"} - semantic #
                      {result.vector_rank ?? "-"}
                    </p>
                  </div>
                ))}
                {searchResultsQuery.data && searchResultsQuery.data.results.length === 0 && (
                  <p className="py-5 text-sm text-slate-500">No matching emails found.</p>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {connectedAccount && (
        <section className="mx-auto max-w-6xl px-6 pb-8">
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <h2 className="text-xl font-semibold text-ink">Latest synced emails</h2>
            <div className="mt-5 divide-y divide-slate-100">
              {(emailsQuery.data ?? []).map((email) => (
                <div key={email.id} className="py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-semibold text-ink">{email.subject ?? "No subject"}</p>
                      <p className="mt-1 text-sm text-slate-500">{email.sender ?? "Unknown sender"}</p>
                    </div>
                    {email.category && (
                      <div className="flex shrink-0 items-center gap-2">
                        {email.priority && (
                          <span
                            className={`rounded-full px-2.5 py-1 text-xs font-medium ${PRIORITY_STYLES[email.priority] ?? "bg-slate-100 text-slate-500"}`}
                          >
                            {email.priority}
                          </span>
                        )}
                        <span className="rounded-full bg-moss/10 px-2.5 py-1 text-xs font-medium text-moss">
                          {CATEGORY_LABELS[email.category] ?? email.category}
                        </span>
                        {email.needs_reply && (
                          <span className="rounded-full bg-coral/10 px-2.5 py-1 text-xs font-medium text-coral">
                            Needs reply
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{email.snippet}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {connectedAccount && Boolean(threadsQuery.data?.length) && (
        <section className="mx-auto max-w-6xl px-6 pb-8">
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <h2 className="text-xl font-semibold text-ink">Thread summaries</h2>
            <div className="mt-5 divide-y divide-slate-100">
              {(threadsQuery.data ?? []).map((thread) => (
                <div key={thread.id} className="py-4">
                  <p className="font-semibold text-ink">{thread.subject ?? "No subject"}</p>
                  <p className="mt-2 text-sm text-slate-600">
                    {thread.summary ?? "Not summarized yet - run AI classification to generate one."}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}



