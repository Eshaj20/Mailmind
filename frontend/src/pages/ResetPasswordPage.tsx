import { useMutation } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { confirmPasswordReset } from "../api/client";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [password, setPassword] = useState("");
  const token = searchParams.get("token") ?? "";
  const resetMutation = useMutation({
    mutationFn: () => confirmPasswordReset(token, password),
    onSuccess: () => window.setTimeout(() => navigate("/auth"), 1200),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    resetMutation.mutate();
  }

  return (
    <main className="grid min-h-screen place-items-center bg-mint px-6 py-12">
      <form className="w-full max-w-md rounded-lg bg-white p-8 shadow-panel" onSubmit={submit}>
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-ink text-white">
          <KeyRound size={21} aria-hidden />
        </div>
        <h1 className="mt-6 text-2xl font-semibold text-ink">Choose a new password</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">Use at least 8 characters. This link can only be used once.</p>
        {!token && <p className="mt-4 rounded-lg bg-coral/10 px-4 py-3 text-sm text-coral">This reset link is incomplete.</p>}
        <label className="mt-6 block">
          <span className="text-sm font-medium text-slate-700">New password</span>
          <input
            className="mt-2 w-full rounded-lg border border-slate-200 px-4 py-3 text-ink outline-none focus:border-moss focus:ring-2 focus:ring-moss/20"
            type="password"
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoComplete="new-password"
          />
        </label>
        {resetMutation.isError && <p className="mt-4 rounded-lg bg-coral/10 px-4 py-3 text-sm text-coral">{resetMutation.error.message}</p>}
        {resetMutation.isSuccess && <p className="mt-4 rounded-lg bg-mint px-4 py-3 text-sm text-ink">{resetMutation.data.detail}</p>}
        <button
          className="mt-6 inline-flex w-full items-center justify-center rounded-lg bg-ink px-5 py-3 font-semibold text-white transition hover:bg-moss disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          disabled={!token || resetMutation.isPending || resetMutation.isSuccess}
        >
          {resetMutation.isPending ? "Updating..." : "Update password"}
        </button>
        <Link className="mt-5 block text-center text-sm font-medium text-moss hover:text-ink" to="/auth">Back to login</Link>
      </form>
    </main>
  );
}
