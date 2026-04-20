"use client";

import { FormEvent, useState } from "react";

const interests = [
  "Credit Rating Simulation",
  "Credit Rating Advisory",
  "TReDS Enablement",
  "Listing Advisory",
];

export function LeadForm() {
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
  }

  return (
    <div className="relative overflow-hidden rounded-[1.7rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06)_0%,rgba(255,255,255,0.03)_100%)] p-5 shadow-[0_28px_70px_rgba(0,0,0,0.28)] backdrop-blur-xl sm:rounded-[2.2rem] sm:p-8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(200,169,106,0.18),transparent_24%)]" />
      <div className="absolute -right-16 top-8 h-40 w-40 rounded-full bg-gold/10 blur-3xl" />

      <div className="relative mb-6">
        <p className="text-[0.72rem] uppercase tracking-[0.22em] text-goldSoft sm:text-sm sm:tracking-[0.28em]">Request a conversation</p>
        <h3 className="mt-3 font-display text-[1.72rem] leading-[1.02] text-cloud sm:text-4xl sm:leading-none">Start with clarity, not guesswork.</h3>
        <p className="mt-3.5 max-w-xl text-[0.92rem] leading-7 text-cloud/72 sm:mt-4 sm:text-sm">
          Tell us what you are evaluating. We will help you frame the right rating strategy, TReDS readiness path,
          or advisory scope.
        </p>
      </div>

      <form className="relative grid gap-4" onSubmit={handleSubmit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-2 text-sm text-cloud/76">
            <span>Name</span>
            <input
              required
              type="text"
              placeholder="Your full name"
              className="rounded-2xl border border-white/12 bg-[#09192c]/75 px-4 py-3.5 text-[16px] text-cloud placeholder:text-cloud/32 outline-none transition focus:border-gold/60 focus:bg-[#0b1e33]"
            />
          </label>
          <label className="grid gap-2 text-sm text-cloud/76">
            <span>Company</span>
            <input
              required
              type="text"
              placeholder="Company name"
              className="rounded-2xl border border-white/12 bg-[#09192c]/75 px-4 py-3.5 text-[16px] text-cloud placeholder:text-cloud/32 outline-none transition focus:border-gold/60 focus:bg-[#0b1e33]"
            />
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-2 text-sm text-cloud/76">
            <span>Email</span>
            <input
              required
              type="email"
              placeholder="name@company.com"
              className="rounded-2xl border border-white/12 bg-[#09192c]/75 px-4 py-3.5 text-[16px] text-cloud placeholder:text-cloud/32 outline-none transition focus:border-gold/60 focus:bg-[#0b1e33]"
            />
          </label>
          <label className="grid gap-2 text-sm text-cloud/76">
            <span>Phone</span>
            <input
              required
              type="tel"
              placeholder="+91"
              className="rounded-2xl border border-white/12 bg-[#09192c]/75 px-4 py-3.5 text-[16px] text-cloud placeholder:text-cloud/32 outline-none transition focus:border-gold/60 focus:bg-[#0b1e33]"
            />
          </label>
        </div>
        <label className="grid gap-2 text-sm text-cloud/76">
          <span>Service interest</span>
          <select className="rounded-2xl border border-white/12 bg-[#09192c]/75 px-4 py-3.5 text-[16px] text-cloud outline-none transition focus:border-gold/60 focus:bg-[#0b1e33]">
            {interests.map((interest) => (
              <option key={interest} value={interest} className="text-ink">
                {interest}
              </option>
            ))}
          </select>
        </label>

        <button
          type="submit"
          className="mt-2 w-full rounded-full bg-gold px-6 py-3.5 text-sm font-semibold text-ink transition hover:bg-[#d8b36d] sm:w-auto"
        >
          Book a Consultation
        </button>

        <div className="min-h-6 text-sm text-goldSoft">
          {submitted ? "Thanks. TreGo Capital will reach out with the next step for your mandate." : null}
        </div>
      </form>
    </div>
  );
}
