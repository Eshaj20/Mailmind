import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain, LogOut, Mail, RefreshCw, Search, ShieldCheck, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import {
  applyCleanupAction,
  classifyEmails,
  clearToken,
  getAIUsageSummary,
  getClassificationSummary,
  getCleanupPreview,
  getEmails,
  getEvaluationReport,
  getGmailAccounts,
  getGmailOAuthUrl,
  getInboxInsights,
  getMe,
  getSenderInsights,
  getSyncHealth,
  getSyncJobs,
  getThreads,
  getToken,
  queueGmailSync,
  searchEmails,
  submitEmailFeedback,
  undoCleanupAction,
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
  const [syncLimit, setSyncLimit] = useState(100);
  const [emailFilters, setEmailFilters] = useState({ category: "", priority: "", is_read: "", needs_reply: "", sender: "", offset: 0 });
  const [selectedCleanupIds, setSelectedCleanupIds] = useState<number[]>([]);
  const [lastCleanupActionIds, setLastCleanupActionIds] = useState<number[]>([]);
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
    queryKey: ["emails", emailFilters],
    queryFn: () => getEmails({ ...emailFilters, limit: 5 }),
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
  const syncHealthQuery = useQuery({
    queryKey: ["sync-health"],
    queryFn: getSyncHealth,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
    refetchInterval: 5000,
  });
  const aiUsageQuery = useQuery({
    queryKey: ["ai-usage"],
    queryFn: getAIUsageSummary,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });
  const classificationSummaryQuery = useQuery({
    queryKey: ["classification-summary"],
    queryFn: getClassificationSummary,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });
  const inboxInsightsQuery = useQuery({
    queryKey: ["inbox-insights"],
    queryFn: getInboxInsights,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });
  const cleanupPreviewQuery = useQuery({
    queryKey: ["cleanup-preview"],
    queryFn: () => getCleanupPreview(),
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });
  const senderInsightsQuery = useQuery({
    queryKey: ["sender-insights"],
    queryFn: getSenderInsights,
    enabled: hasToken && Boolean(accountsQuery.data?.length),
    retry: false,
  });
  const evaluationReportQuery = useQuery({
    queryKey: ["classification-evaluation"],
    queryFn: getEvaluationReport,
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
    mutationFn: ({ accountId, maxResults }: { accountId?: number; maxResults: number }) => queueGmailSync(accountId, maxResults),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["sender-insights"] });
    },
  });
  const cleanupActionMutation = useMutation({
    mutationFn: ({ emailId, action }: { emailId: number; action: "archive" | "mark_read" }) =>
      applyCleanupAction([emailId], action),
    onSuccess: (data) => {
      setLastCleanupActionIds(data.action_ids);
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["sender-insights"] });
    },
  });
  const bulkCleanupActionMutation = useMutation({
    mutationFn: (action: "archive" | "mark_read") => applyCleanupAction(selectedCleanupIds, action),
    onSuccess: (data) => {
      setSelectedCleanupIds([]);
      setLastCleanupActionIds(data.action_ids);
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["sender-insights"] });
    },
  });
  const undoCleanupMutation = useMutation({
    mutationFn: async (actionIds: number[]) => Promise.all(actionIds.map((actionId) => undoCleanupAction(actionId))),
    onSuccess: () => {
      setLastCleanupActionIds([]);
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
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
        note: "User marked this cleanup suggestion as not useful.",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["classification-summary"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["sender-insights"] });
    },
  });
  const classifyMutation = useMutation({
    mutationFn: classifyEmails,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["classification-summary"] });
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-insights"] });
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] });
      queryClient.invalidateQueries({ queryKey: ["sender-insights"] });
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
  const isDemoWorkspace = connectedAccount?.google_email.endsWith("@mailmind.dev") ?? false;
  const workspaceMode = isDemoWorkspace ? "Demo Inbox Mode" : connectedAccount ? "Real Gmail Mode" : "Setup Mode";
  const workspaceModeCopy = isDemoWorkspace
    ? "Synthetic emails for safe recruiter/user walkthroughs. No personal Gmail data is exposed."
    : connectedAccount
      ? "Real Gmail account connected through OAuth. Cleanup actions require explicit review."
      : "Connect Gmail or seed demo data to start exploring MailMind.";
  const latestJob = syncJobsQuery.data?.[0];
  const summary = classificationSummaryQuery.data;
  const emailPage = emailsQuery.data;
  const cleanupPreviewItems = cleanupPreviewQuery.data?.items ?? [];
  const visibleCleanupPreviewItems = cleanupPreviewItems.slice(0, 6);
  const hasUnclassified = Boolean(summary && summary.total_unclassified > 0);
  const evalSampleSize = evaluationReportQuery.data?.report_markdown.match(/Sample size: (\d+)/)?.[1];
  const evalCategoryF1 = evaluationReportQuery.data?.report_markdown.match(/Category[\s\S]*?Macro F1: ([0-9.]+)/)?.[1];

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

      <section className="mx-auto max-w-6xl px-6 pt-8">
        <div className={`rounded-lg border p-4 ${isDemoWorkspace ? "border-amber-200 bg-amber-50" : connectedAccount ? "border-moss/20 bg-moss/10" : "border-slate-200 bg-white"}`}>
          <p className="text-sm font-semibold text-ink">{workspaceMode}</p>
          <p className="mt-1 text-sm text-slate-600">{workspaceModeCopy}</p>
        </div>
      </section>

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
            {isDemoWorkspace
              ? `${connectedAccount?.google_email} is a seeded demo inbox for safe walkthroughs.`
              : connectedAccount
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
              disabled={connectMutation.isPending || isDemoWorkspace}
              onClick={() => connectMutation.mutate()}
            >
              <Mail size={18} aria-hidden />
              {isDemoWorkspace ? "Demo Gmail seeded" : connectedAccount ? "Reconnect Gmail" : connectMutation.isPending ? "Opening Google..." : "Connect Gmail"}
            </button>
            {connectedAccount && (
              <div className="grid gap-2">
                <select
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-moss"
                  value={syncLimit}
                  onChange={(event) => setSyncLimit(Number(event.target.value))}
                >
                  <option value={25}>25 emails</option>
                  <option value={100}>100 emails</option>
                  <option value={500}>500 emails</option>
                </select>
                <button
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-3 font-semibold text-ink hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  type="button"
                  disabled={syncMutation.isPending || isDemoWorkspace}
                  onClick={() => syncMutation.mutate({ accountId: connectedAccount.id, maxResults: syncLimit })}
                >
                  <RefreshCw size={18} aria-hidden />
                  {isDemoWorkspace ? "Sync disabled in demo" : syncMutation.isPending ? "Queueing sync..." : `Queue ${syncLimit}-email sync`}
                </button>
              </div>
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
                {latestJob.processed_count}/{latestJob.max_results} processed, {latestJob.created_count} created, {latestJob.updated_count} updated, attempt {latestJob.attempt_count}
                /{latestJob.max_attempts}
              </p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-moss" style={{ width: `${latestJob.progress_percent}%` }} />
              </div>
              <p className="mt-1 text-xs text-slate-500">{latestJob.progress_percent}% complete</p>
            </div>
          )}
          {syncHealthQuery.data && (
            <div className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="font-semibold text-ink">Sync health</p>
                <p className="mt-1 text-slate-500">
                  {syncHealthQuery.data.succeeded_jobs} succeeded, {syncHealthQuery.data.retrying_jobs} retrying, {syncHealthQuery.data.failed_jobs} failed
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="font-semibold text-ink">Average sync</p>
                <p className="mt-1 text-slate-500">{syncHealthQuery.data.avg_synced_count} emails/job</p>
              </div>
            </div>
          )}        </aside>
      </section>


      {connectedAccount && inboxInsightsQuery.data && (
        <section className="mx-auto max-w-6xl px-6 pb-8">
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-ink">Inbox health</h2>
                <p className="mt-1 text-sm text-slate-500">Formula-based score with cleanup recommendations.</p>
              </div>
              <div className="rounded-lg bg-ink px-5 py-4 text-center text-white">
                <p className="text-3xl font-semibold">{inboxInsightsQuery.data.score}</p>
                <p className="text-xs uppercase tracking-wide text-white/70">Health score</p>
              </div>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <div className="rounded-lg border border-slate-200 p-4">
                <p className="text-2xl font-semibold text-ink">{inboxInsightsQuery.data.unread_count}</p>
                <p className="text-sm text-slate-500">Unread</p>
              </div>
              <div className="rounded-lg border border-slate-200 p-4">
                <p className="text-2xl font-semibold text-ink">{inboxInsightsQuery.data.high_priority_unread_count}</p>
                <p className="text-sm text-slate-500">Priority unread</p>
              </div>
              <div className="rounded-lg border border-slate-200 p-4">
                <p className="text-2xl font-semibold text-ink">{inboxInsightsQuery.data.pending_reply_count}</p>
                <p className="text-sm text-slate-500">Need reply</p>
                {inboxInsightsQuery.data.aged_follow_up_count > 0 && (
                  <p className="mt-1 text-xs text-coral">
                    {inboxInsightsQuery.data.aged_follow_up_count} older than {inboxInsightsQuery.data.follow_up_age_days}d
                  </p>
                )}
              </div>
              <div className="rounded-lg border border-slate-200 p-4">
                <p className="text-2xl font-semibold text-ink">{inboxInsightsQuery.data.cleanup_candidate_count}</p>
                <p className="text-sm text-slate-500">Cleanup candidates</p>
              </div>
            </div>
            {inboxInsightsQuery.data.suggestions.length > 0 && (
              <div className="mt-5 grid gap-3 lg:grid-cols-3">
                {inboxInsightsQuery.data.suggestions.map((suggestion) => (
                  <div key={suggestion.suggestion_type} className="rounded-lg border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="font-semibold text-ink">{suggestion.title}</p>
                      <span className="rounded-full bg-moss/10 px-2.5 py-1 text-xs font-medium text-moss">
                        {Math.round(suggestion.confidence * 100)}%
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{suggestion.description}</p>
                    {suggestion.oldest_days_pending !== null && (
                      <p className="mt-2 text-xs font-medium text-coral">
                        Oldest pending: {suggestion.oldest_days_pending} days
                      </p>
                    )}
                    {suggestion.sender_breakdown.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {suggestion.sender_breakdown.slice(0, 3).map((sender) => (
                          <span
                            key={`${suggestion.suggestion_type}-${sender.sender}`}
                            className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600"
                          >
                            {sender.count} from {sender.sender}
                          </span>
                        ))}
                      </div>
                    )}
                    {suggestion.candidate_emails.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {suggestion.candidate_emails.slice(0, 3).map((email) => (
                          <div key={email.id} className="rounded-lg bg-slate-50 px-3 py-2">
                            <p className="truncate text-sm font-medium text-ink">{email.subject ?? "No subject"}</p>
                            <p className="truncate text-xs text-slate-500">{email.sender ?? "Unknown sender"}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    <p className="mt-3 text-xs text-slate-400">
                      {suggestion.email_count} emails - saves about {suggestion.estimated_time_saved_minutes} min
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}


      {connectedAccount && (cleanupPreviewQuery.data || Boolean(senderInsightsQuery.data?.length)) && (
        <section className="mx-auto grid max-w-6xl gap-6 px-6 pb-8 lg:grid-cols-2">
          {cleanupPreviewQuery.data && (
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center justify-between gap-3">
                <h2 className="text-xl font-semibold text-ink">Archive preview</h2>
                <Link className="rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-white hover:bg-moss" to="/cleanup">
                  Review cleanup
                </Link>
              </div>
                  <p className="mt-1 text-sm text-slate-500">
                    {cleanupPreviewQuery.data.total_candidates} safe candidates before any Gmail action.
                  </p>
                </div>
                <span className="rounded-full bg-moss/10 px-3 py-1 text-sm font-medium text-moss">
                  {cleanupPreviewQuery.data.estimated_time_saved_minutes} min
                </span>
              </div>
              {cleanupPreviewItems.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    type="button"
                    onClick={() => setSelectedCleanupIds(visibleCleanupPreviewItems.map((item) => item.email.id))}
                  >
                    Select visible
                  </button>
                  <button
                    className="rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-white hover:bg-moss disabled:opacity-60"
                    type="button"
                    disabled={selectedCleanupIds.length === 0 || bulkCleanupActionMutation.isPending}
                    onClick={() => bulkCleanupActionMutation.mutate("archive")}
                  >
                    Archive {selectedCleanupIds.length || "selected"}
                  </button>
                  <button
                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    type="button"
                    disabled={selectedCleanupIds.length === 0 || bulkCleanupActionMutation.isPending}
                    onClick={() => bulkCleanupActionMutation.mutate("mark_read")}
                  >
                    Mark read
                  </button>
                </div>
              )}
              {lastCleanupActionIds.length > 0 && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm font-medium text-ink">
                      Last cleanup changed {lastCleanupActionIds.length} email
                      {lastCleanupActionIds.length === 1 ? "" : "s"}.
                    </p>
                    <button
                      className="rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-white hover:bg-moss disabled:opacity-60"
                      type="button"
                      disabled={undoCleanupMutation.isPending}
                      onClick={() => undoCleanupMutation.mutate(lastCleanupActionIds)}
                    >
                      {undoCleanupMutation.isPending ? "Undoing..." : "Undo last cleanup"}
                    </button>
                  </div>
                </div>
              )}
              <div className="mt-5 space-y-3">
                {visibleCleanupPreviewItems.map((item) => (
                  <div key={item.email.id} className="rounded-lg border border-slate-100 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{item.email.subject ?? "No subject"}</p>
                        <p className="truncate text-xs text-slate-500">{item.email.sender ?? "Unknown sender"}</p>
                      </div>
                      <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                        {Math.round(item.confidence * 100)}%
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">{item.reason}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className="rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-white hover:bg-moss disabled:opacity-60"
                        type="button"
                        disabled={cleanupActionMutation.isPending}
                        onClick={() => cleanupActionMutation.mutate({ emailId: item.email.id, action: "archive" })}
                      >
                        Archive
                      </button>
                      <button
                        className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                        type="button"
                        disabled={cleanupActionMutation.isPending}
                        onClick={() => cleanupActionMutation.mutate({ emailId: item.email.id, action: "mark_read" })}
                      >
                        Mark read
                      </button>
                      <button
                        className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-50 disabled:opacity-60"
                        type="button"
                        disabled={feedbackMutation.isPending}
                        onClick={() => feedbackMutation.mutate(item.email.id)}
                      >
                        Not cleanup
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {Boolean(senderInsightsQuery.data?.length) && (
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-xl font-semibold text-ink">Sender intelligence</h2>
              <div className="mt-5 space-y-3">
                {(senderInsightsQuery.data ?? []).slice(0, 5).map((sender) => (
                  <div key={sender.sender} className="rounded-lg border border-slate-100 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{sender.sender}</p>
                        <p className="text-xs text-slate-500">
                          {sender.total_emails} emails - {sender.cleanup_candidate_count} cleanup - {sender.unread_count} unread
                        </p>
                      </div>
                      <span className="shrink-0 rounded-full bg-moss/10 px-2.5 py-1 text-xs font-medium text-moss">
                        {sender.suggested_action.replace(/_/g, " ")}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
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
            {(evalSampleSize || evalCategoryF1) && (
              <div className="mt-4 rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
                Eval set: {evalSampleSize ?? "-"} emails | Category macro F1: {evalCategoryF1 ?? "-"}
              </div>
            )}
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
            <div className="mt-4 grid gap-3 md:grid-cols-5">
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-moss" value={emailFilters.category} onChange={(event) => setEmailFilters({ ...emailFilters, category: event.target.value, offset: 0 })}>
                <option value="">All categories</option>
                <option value="primary">Primary</option>
                <option value="promotions">Promotions</option>
                <option value="social">Social</option>
                <option value="updates">Updates</option>
                <option value="spam">Spam</option>
              </select>
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-moss" value={emailFilters.priority} onChange={(event) => setEmailFilters({ ...emailFilters, priority: event.target.value, offset: 0 })}>
                <option value="">All priorities</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-moss" value={emailFilters.is_read} onChange={(event) => setEmailFilters({ ...emailFilters, is_read: event.target.value, offset: 0 })}>
                <option value="">Read state</option>
                <option value="false">Unread</option>
                <option value="true">Read</option>
              </select>
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-moss" value={emailFilters.needs_reply} onChange={(event) => setEmailFilters({ ...emailFilters, needs_reply: event.target.value, offset: 0 })}>
                <option value="">Reply state</option>
                <option value="true">Needs reply</option>
                <option value="false">No reply needed</option>
              </select>
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-moss" placeholder="Filter sender" value={emailFilters.sender} onChange={(event) => setEmailFilters({ ...emailFilters, sender: event.target.value, offset: 0 })} />
            </div>
            <div className="mt-5 divide-y divide-slate-100">
              {(emailPage?.items ?? []).map((email) => (
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


      {connectedAccount && emailPage && emailPage.total > 0 && (
        <section className="mx-auto max-w-6xl px-6 pb-8">
          <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
            <span>
              Showing {emailPage.offset + 1}-{emailPage.offset + emailPage.items.length} of {emailPage.total}
            </span>
            <div className="flex gap-2">
              <button className="rounded-lg border border-slate-200 px-3 py-1.5 font-semibold disabled:opacity-50" type="button" disabled={emailPage.offset === 0} onClick={() => setEmailFilters({ ...emailFilters, offset: Math.max(0, emailFilters.offset - 5) })}>
                Previous page
              </button>
              <button className="rounded-lg border border-slate-200 px-3 py-1.5 font-semibold disabled:opacity-50" type="button" disabled={!emailPage.has_more} onClick={() => setEmailFilters({ ...emailFilters, offset: emailFilters.offset + 5 })}>
                Next page
              </button>
            </div>
          </div>
        </section>
      )}      {connectedAccount && Boolean(threadsQuery.data?.length) && (
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









