import { useQuery } from "@tanstack/react-query";
import { Brain, LogOut, Mail, Search, ShieldCheck, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { clearToken, getMe, getToken } from "../api/client";

// Milestones for the dashboard page
const milestones = [
  { label: "Gmail sync", value: "Week 2", icon: Mail },
  { label: "AI classification", value: "Week 4", icon: Brain },
  { label: "Semantic search", value: "Week 5", icon: Search },
  { label: "Inbox intelligence", value: "Week 6", icon: Sparkles },
];

// DashboardPage component for displaying user dashboard and milestones
export function DashboardPage() {
  const navigate = useNavigate();
  const hasToken = Boolean(getToken());
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: hasToken,
    retry: false,
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
          <h2 className="text-xl font-semibold text-ink">Week 1 foundation</h2>
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
          <h2 className="text-xl font-semibold text-ink">Next build target</h2>
          <p className="mt-3 text-slate-600">
            Add Google OAuth, store refresh tokens securely, then persist the first Gmail sync into
            PostgreSQL.
          </p>
          <button
            className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-3 font-semibold text-ink"
            type="button"
            disabled
          >
            <Mail size={18} aria-hidden />
            Connect Gmail
          </button>
        </aside>
      </section>
    </main>
  );
}
