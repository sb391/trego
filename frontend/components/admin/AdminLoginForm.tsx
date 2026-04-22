"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { getSupabaseBrowserClient } from "../../lib/supabase/browser";

export function AdminLoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/admin";
  const reason = searchParams.get("reason");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [state, setState] = useState<{
    status: "idle" | "submitting" | "success" | "error";
    message: string | null;
  }>({
    status: "idle",
    message: null,
  });

  const supabase = useMemo(() => getSupabaseBrowserClient(), []);

  const helperMessage =
    reason === "unauthorized"
      ? "This email is not approved for the TreGo admin console."
      : reason === "config"
        ? "Supabase browser auth is not configured yet. Add the public URL and anon key to continue."
        : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!supabase) {
      setState({
        status: "error",
        message: "Supabase browser auth is not configured yet.",
      });
      return;
    }

    setState({ status: "submitting", message: null });

    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });

    if (error) {
      setState({
        status: "error",
        message: error.message,
      });
      return;
    }

    setState({
      status: "success",
      message: "Sign-in successful. Taking you into the admin console...",
    });
    router.replace(nextPath);
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {helperMessage ? (
        <div className="rounded-[0.95rem] border border-[#eadbd4] bg-[#fff7f4] px-4 py-3 text-[0.92rem] leading-6 text-[#8a553e]">
          {helperMessage}
        </div>
      ) : null}

      <label className="grid gap-2">
        <span className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#95a4b6]">Admin email</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="admin@tregocapital.com"
          className="rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 py-3.5 text-[1rem] text-[#182039] outline-none transition focus:border-[#d1c2c7]"
          required
        />
      </label>

      <label className="grid gap-2">
        <span className="text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[#95a4b6]">Password</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Enter your admin password"
          className="rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 py-3.5 text-[1rem] text-[#182039] outline-none transition focus:border-[#d1c2c7]"
          required
        />
      </label>

      {state.message ? (
        <div
          className={[
            "rounded-[0.95rem] border px-4 py-3 text-[0.92rem] leading-6",
            state.status === "success"
              ? "border-[#cee4d1] bg-[#f4fbf6] text-[#2f6b44]"
              : "border-[#edd4d4] bg-[#fff7f7] text-[#8e3b3b]",
          ].join(" ")}
        >
          {state.message}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={state.status === "submitting"}
        className="interactive-press inline-flex min-h-12 w-full items-center justify-center rounded-[0.98rem] border border-[#7f3922] bg-[#853921] px-6 py-3.5 text-[0.78rem] font-semibold uppercase tracking-[0.1em] text-white shadow-[0_14px_24px_rgba(133,57,33,0.24)] transition hover:bg-[#73301b] disabled:cursor-not-allowed disabled:opacity-70"
      >
        {state.status === "submitting" ? "Signing in..." : "Access admin console"}
      </button>
    </form>
  );
}
