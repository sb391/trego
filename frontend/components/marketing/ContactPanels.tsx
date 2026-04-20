"use client";

import { OfficeAccordionList } from "./OfficeAccordion";

export function ContactFormPanel() {
  return (
    <div className="rounded-[1.5rem] border border-[#ece2e6] bg-white px-5 py-6 shadow-[0_14px_36px_rgba(10,37,64,0.04)] sm:rounded-[1.8rem] sm:px-7 sm:py-8">
      <h3 className="text-[1.55rem] font-bold tracking-[-0.04em] text-[#2f255f] sm:text-[2rem]">Send Us a Message</h3>
      <p className="mt-3 text-[0.95rem] leading-7 text-[#6c7d8f] sm:text-[1rem] sm:leading-8">
        Fill out the form below and a member of our team will respond within 24 hours.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {[
          { label: "Full Name *", placeholder: "Your full name" },
          { label: "Email Address *", placeholder: "you@company.com" },
          { label: "Company", placeholder: "Your organization" },
          { label: "Inquiry Type", placeholder: "Select a service", select: true },
        ].map((field) => (
          <label key={field.label} className="grid gap-2 text-sm text-[#90a2b6]">
            <span className="uppercase tracking-[0.14em]">{field.label}</span>
            {field.select ? (
              <div className="relative">
                <select className="appearance-none rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 py-3.5 pr-14 text-[16px] text-[#182039] outline-none transition focus:border-[#d1c2c7] sm:py-4">
                  <option>{field.placeholder}</option>
                  <option>Credit Rating Simulation</option>
                  <option>Credit Rating Advisory</option>
                  <option>TReDS Enablement</option>
                  <option>Capital & Listing Strategy</option>
                </select>
                <span className="pointer-events-none absolute inset-y-0 right-5 flex items-center text-[#182039]">
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 20 20"
                    fill="none"
                    className="h-4 w-4"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="m5 7 5 6 5-6" />
                  </svg>
                </span>
              </div>
            ) : (
              <input
                type="text"
                placeholder={field.placeholder}
                className="rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 py-3.5 text-[16px] text-[#182039] placeholder:text-[#a7b4bf] outline-none transition focus:border-[#d1c2c7] sm:py-4"
              />
            )}
          </label>
        ))}
      </div>

      <label className="mt-4 grid gap-2 text-sm text-[#90a2b6]">
        <span className="uppercase tracking-[0.14em]">Message *</span>
        <textarea
          rows={7}
          placeholder="Tell us about your requirements..."
          className="rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 py-3.5 text-[16px] text-[#182039] placeholder:text-[#a7b4bf] outline-none transition focus:border-[#d1c2c7] sm:py-4"
        />
      </label>

      <button
        type="button"
        className="interactive-press mt-6 inline-flex w-full items-center justify-center rounded-[0.95rem] border border-[#7f3922] bg-[#853921] px-8 py-4 text-sm font-semibold uppercase tracking-[0.08em] text-white shadow-[0_14px_24px_rgba(133,57,33,0.28)] transition hover:bg-[#73301b] hover:shadow-[0_18px_30px_rgba(115,48,27,0.32)] sm:w-auto"
      >
        Submit Inquiry
      </button>
    </div>
  );
}

export function ContactSidePanel() {
  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="rounded-[1.5rem] border border-[#ece2e6] bg-white px-5 py-6 shadow-[0_14px_34px_rgba(10,37,64,0.04)] sm:rounded-[1.7rem] sm:px-6 sm:py-7">
        <h3 className="text-[1.55rem] font-bold tracking-[-0.04em] text-[#2f255f] sm:text-[2rem]">Direct Contact</h3>
        <div className="mt-8 space-y-6">
          <div className="flex gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#f7efed] text-[#b45a3c]">☎</div>
            <div>
              <div className="text-[0.84rem] uppercase tracking-[0.14em] text-[#8fa0b4]">Phone</div>
              <div className="mt-1 text-[1rem] font-semibold text-[#2f255f] sm:text-[1.2rem]">+91-7506429193</div>
            </div>
          </div>
          <div className="flex gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#f7efed] text-[#b45a3c]">@</div>
            <div>
              <div className="text-[0.84rem] uppercase tracking-[0.14em] text-[#8fa0b4]">Email</div>
              <div className="mt-1 break-all text-[0.98rem] font-semibold text-[#2f255f] sm:text-[1.1rem]">contact@tregocapital.com</div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-[1.5rem] border border-[#ece2e6] bg-white px-5 py-6 shadow-[0_14px_34px_rgba(10,37,64,0.04)] sm:rounded-[1.7rem] sm:px-6 sm:py-7">
        <h3 className="text-[1.55rem] font-bold tracking-[-0.04em] text-[#2f255f] sm:text-[2rem]">Our Offices</h3>
        <div className="mt-8">
          <OfficeAccordionList />
        </div>
      </div>
    </div>
  );
}
