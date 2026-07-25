import { useMutation, useQuery } from "@tanstack/react-query";
import { Brain, LogOut, Mail, Search, ShieldCheck, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import {
  clearToken,
  getEmails,
  getGmailAccounts,
  getGmailOAuthUrl,
  getMe,
  getToken,
} from "../api/client";

const milestones = [
  { label: "Gmail sync", value: "Week 2", icon: Mail },
  { label: "AI classification", value: "Week 4", icon: Brain },
  { label: "Hybrid search", value: "Week 5", icon: Search },
  { label: "Inbox intelligence", value: "Week 6", icon: Sparkles },
];

export function DashboardPage() {
  const navigate = useNavigate();
  const hasToken = Boolean(getToken());
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
  const connectMutation = useMutation({
    mutationFn: getGmailOAuthUrl,
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
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
          <h2 className="text-xl font-semibold text-ink">Week 2 Gmail integration</h2>
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
              ? `${connectedAccount.google_email} is ready for first-sync and re-sync testing.`
              : "Start Google OAuth, store the refresh token securely, and persist the first Gmail sync."}
          </p>
          {connectMutation.isError && (
            <p className="mt-4 rounded-lg bg-coral/10 px-4 py-3 text-sm text-coral">
              {connectMutation.error.message}
            </p>
          )}
          <button
            className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-4 py-3 font-semibold text-white hover:bg-moss disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            disabled={connectMutation.isPending}
            onClick={() => connectMutation.mutate()}
          >
            <Mail size={18} aria-hidden />
            {connectedAccount ? "Reconnect Gmail" : connectMutation.isPending ? "Opening Google..." : "Connect Gmail"}
          </button>
        </aside>
      </section>

      {connectedAccount && (
        <section className="mx-auto max-w-6xl px-6 pb-8">
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <h2 className="text-xl font-semibold text-ink">Latest synced emails</h2>
            <div className="mt-5 divide-y divide-slate-100">
              {(emailsQuery.data ?? []).map((email) => (
                <div key={email.id} className="py-4">
                  <p className="font-semibold text-ink">{email.subject ?? "No subject"}</p>
                  <p className="mt-1 text-sm text-slate-500">{email.sender ?? "Unknown sender"}</p>
                  <p className="mt-2 text-sm text-slate-600">{email.snippet}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
