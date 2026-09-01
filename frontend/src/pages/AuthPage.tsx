import { useMutation } from "@tanstack/react-query";
import { Inbox, LogIn, PlayCircle, UserPlus } from "lucide-react";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { login, signup } from "../api/client";

type AuthForm = {
  mode: "login" | "signup";
  email: string;
  password: string;
  fullName?: string;
};

// AuthPage component for user authentication (signup/login)
export function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");

  // useMutation hook for handling authentication (signup/login)
  const authMutation = useMutation({
    mutationFn: async (form: AuthForm) => {
      if (form.mode === "signup") {
        await signup({ email: form.email, password: form.password, full_name: form.fullName || undefined });
      }
      return login(form.email, form.password);
    },
    onSuccess: () => navigate("/"),
  });

  // Handle form submission for authentication
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    authMutation.mutate({ mode, email, password, fullName });
  }

  function useDemoWorkspace() {
    setMode("login");
    setEmail("demo@mailmind.dev");
    setPassword("DemoPass123!");
    setFullName("");
    authMutation.mutate({ mode: "login", email: "demo@mailmind.dev", password: "DemoPass123!" });
  }

  return (
    <main className="grid min-h-screen bg-mint lg:grid-cols-[1fr_480px]">
      <section className="flex items-center px-6 py-12 sm:px-10 lg:px-16">
        <div className="max-w-3xl">
          <div className="mb-8 flex h-12 w-12 items-center justify-center rounded-lg bg-ink text-white">
            <Inbox size={24} aria-hidden />
          </div>
          <h1 className="max-w-2xl text-5xl font-semibold tracking-normal text-ink sm:text-6xl">
            MailMind
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-ink/70">
            A production-minded AI inbox assistant for Gmail sync, classification, summaries,
            semantic search, and weekly email intelligence.
          </p>
        </div>
      </section>

      <section className="flex items-center bg-white px-6 py-10 shadow-panel sm:px-10">
        <form className="w-full" onSubmit={submit}>
          <div className="mb-8 inline-flex rounded-lg bg-slate-100 p-1">
            <button
              className={`rounded-md px-4 py-2 text-sm font-medium ${
                mode === "signup" ? "bg-white text-ink shadow-sm" : "text-slate-600"
              }`}
              type="button"
              onClick={() => setMode("signup")}
            >
              Signup
            </button>
            <button
              className={`rounded-md px-4 py-2 text-sm font-medium ${
                mode === "login" ? "bg-white text-ink shadow-sm" : "text-slate-600"
              }`}
              type="button"
              onClick={() => setMode("login")}
            >
              Login
            </button>
          </div>

          <h2 className="text-2xl font-semibold text-ink">
            {mode === "signup" ? "Create your workspace" : "Welcome back"}
          </h2>

          <div className="mt-8 space-y-5">
            {mode === "signup" && (
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Full name</span>
                <input
                  className="mt-2 w-full rounded-lg border border-slate-200 px-4 py-3 text-ink outline-none focus:border-moss focus:ring-2 focus:ring-moss/20"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  autoComplete="name"
                />
              </label>
            )}

            <label className="block">
              <span className="text-sm font-medium text-slate-700">Email</span>
              <input
                className="mt-2 w-full rounded-lg border border-slate-200 px-4 py-3 text-ink outline-none focus:border-moss focus:ring-2 focus:ring-moss/20"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                autoComplete="email"
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium text-slate-700">Password</span>
              <input
                className="mt-2 w-full rounded-lg border border-slate-200 px-4 py-3 text-ink outline-none focus:border-moss focus:ring-2 focus:ring-moss/20"
                type="password"
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
              />
            </label>
          </div>

          {authMutation.isError && (
            <p className="mt-4 rounded-lg bg-coral/10 px-4 py-3 text-sm text-coral">
              {authMutation.error.message}
            </p>
          )}

          <button
            className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-5 py-3 font-semibold text-white transition hover:bg-moss disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={authMutation.isPending}
          >
            {mode === "signup" ? <UserPlus size={18} aria-hidden /> : <LogIn size={18} aria-hidden />}
            {authMutation.isPending ? "Working..." : mode === "signup" ? "Create account" : "Login"}
          </button>

          <button
            className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-5 py-3 font-semibold text-ink transition hover:border-moss hover:text-moss"
            type="button"
            disabled={authMutation.isPending}
            onClick={useDemoWorkspace}
          >
            <PlayCircle size={18} aria-hidden />
            Use demo workspace
          </button>
        </form>
      </section>
    </main>
  );
}
