"use client";

import { useState, type FormEvent } from "react";
import { usePathname } from "next/navigation";

import { OfficeAccordionList } from "./OfficeAccordion";
import { INQUIRY_TYPE_OPTIONS } from "../../lib/inquiries";

type ContactTab = "inquiry" | "contact" | "offices";
type InquiryFormState = {
  fullName: string;
  email: string;
  company: string;
  inquiryType: string;
  message: string;
};

export function ContactFormPanel({ compact = false }: { compact?: boolean }) {
  const pathname = usePathname();
  const [formState, setFormState] = useState<InquiryFormState>({
    fullName: "",
    email: "",
    company: "",
    inquiryType: "",
    message: "",
  });
  const [submissionState, setSubmissionState] = useState<{
    status: "idle" | "submitting" | "success" | "error";
    message: string | null;
  }>({
    status: "idle",
    message: null,
  });

  const handleFieldChange = (
    field: keyof InquiryFormState,
    value: string,
  ) => {
    setFormState((current) => ({ ...current, [field]: value }));
    if (submissionState.status !== "idle") {
      setSubmissionState({ status: "idle", message: null });
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmissionState({ status: "submitting", message: null });

    try {
      const response = await fetch("/api/inquiries", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...formState,
          sourcePage: pathname,
        }),
      });

      const payload = (await response.json().catch(() => null)) as
        | { ok?: boolean; error?: string }
        | null;

      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.error || "The inquiry could not be submitted. Please try again.");
      }

      setFormState({
        fullName: "",
        email: "",
        company: "",
        inquiryType: "",
        message: "",
      });
      setSubmissionState({
        status: "success",
        message: "Your inquiry has been received. A member of our team will respond within 24 hours.",
      });
    } catch (error) {
      setSubmissionState({
        status: "error",
        message:
          error instanceof Error
            ? error.message
            : "The inquiry could not be submitted. Please try again.",
      });
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={[
        "rounded-[1.5rem] border border-[#ece2e6] bg-white shadow-[0_14px_36px_rgba(10,37,64,0.04)]",
        compact ? "px-4 py-5 sm:px-5 sm:py-6" : "px-5 py-6 sm:rounded-[1.8rem] sm:px-7 sm:py-8",
      ].join(" ")}
    >
      <h3 className={["font-bold tracking-[-0.04em] text-[#2f255f]", compact ? "text-[1.3rem] sm:text-[1.5rem]" : "text-[1.55rem] sm:text-[2rem]"].join(" ")}>
        Send Us a Message
      </h3>
      <p className={["mt-3 text-[#6c7d8f]", compact ? "text-[0.9rem] leading-[1.7] sm:text-[0.95rem] sm:leading-7" : "text-[0.95rem] leading-7 sm:text-[1rem] sm:leading-8"].join(" ")}>
        Fill out the form below and a member of our team will respond within 24 hours.
      </p>

      <div className={["grid gap-3 sm:gap-4", compact ? "mt-6 grid-cols-1 sm:grid-cols-2" : "mt-8 sm:grid-cols-2"].join(" ")}>
        {[
          { label: "Full Name *", placeholder: "Your full name", field: "fullName" },
          { label: "Email Address *", placeholder: "you@company.com", field: "email", type: "email" },
          { label: "Company *", placeholder: "Your organization", field: "company" },
          { label: "Inquiry Type *", placeholder: "Select a service", select: true, field: "inquiryType" },
        ].map((field) => (
          <label key={field.label} className="grid min-w-0 gap-2 text-sm text-[#90a2b6]">
            <span className={["uppercase text-[#90a2b6]", compact ? "text-[0.68rem] tracking-[0.12em]" : "tracking-[0.14em]"].join(" ")}>
              {field.label}
            </span>
            {field.select ? (
              <div className="relative min-w-0">
                <select
                  value={formState[field.field as keyof InquiryFormState]}
                  onChange={(event) => handleFieldChange(field.field as keyof InquiryFormState, event.target.value)}
                  className={[
                    "w-full min-w-0 appearance-none rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 pr-14 text-[#182039] outline-none transition focus:border-[#d1c2c7]",
                    compact ? "py-3 text-[15px] sm:py-3.5" : "py-3.5 text-[16px] sm:py-4",
                  ].join(" ")}
                  required
                >
                  <option value="" disabled>
                    {field.placeholder}
                  </option>
                  {INQUIRY_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
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
                type={field.type ?? "text"}
                placeholder={field.placeholder}
                value={formState[field.field as keyof InquiryFormState]}
                onChange={(event) => handleFieldChange(field.field as keyof InquiryFormState, event.target.value)}
                className={[
                  "w-full min-w-0 rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 text-[#182039] placeholder:text-[#a7b4bf] outline-none transition focus:border-[#d1c2c7]",
                  compact ? "py-3 text-[15px] sm:py-3.5" : "py-3.5 text-[16px] sm:py-4",
                ].join(" ")}
                required
              />
            )}
          </label>
        ))}
      </div>

      <label className={["grid gap-2 text-sm text-[#90a2b6]", compact ? "mt-3" : "mt-4"].join(" ")}>
        <span className={["uppercase text-[#90a2b6]", compact ? "text-[0.68rem] tracking-[0.12em]" : "tracking-[0.14em]"].join(" ")}>
          Message *
        </span>
        <textarea
          rows={compact ? 5 : 7}
          placeholder="Tell us about your requirements..."
          value={formState.message}
          onChange={(event) => handleFieldChange("message", event.target.value)}
          className={[
            "w-full rounded-[0.95rem] border border-[#e4d9de] bg-[#fcfaf8] px-4 text-[#182039] placeholder:text-[#a7b4bf] outline-none transition focus:border-[#d1c2c7]",
            compact ? "py-3 text-[15px] sm:py-3.5" : "py-3.5 text-[16px] sm:py-4",
          ].join(" ")}
          required
        />
      </label>

      {submissionState.message ? (
        <div
          className={[
            "mt-4 rounded-[0.9rem] border px-4 py-3 text-[0.9rem] leading-6",
            submissionState.status === "success"
              ? "border-[#cfe6d7] bg-[#f4fbf6] text-[#2f6b44]"
              : "border-[#edd4d4] bg-[#fff7f7] text-[#8e3b3b]",
          ].join(" ")}
        >
          {submissionState.message}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={submissionState.status === "submitting"}
        className={[
          "interactive-press inline-flex w-full items-center justify-center rounded-[0.95rem] border border-[#7f3922] bg-[#853921] px-8 text-sm font-semibold uppercase tracking-[0.08em] text-white shadow-[0_14px_24px_rgba(133,57,33,0.28)] transition hover:bg-[#73301b] hover:shadow-[0_18px_30px_rgba(115,48,27,0.32)] disabled:cursor-not-allowed disabled:opacity-70 sm:w-auto",
          compact ? "mt-5 py-3.5" : "mt-6 py-4",
        ].join(" ")}
      >
        {submissionState.status === "submitting" ? "Submitting..." : "Submit Inquiry"}
      </button>
    </form>
  );
}

function ContactDirectCard({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={[
        "rounded-[1.5rem] border border-[#ece2e6] bg-white shadow-[0_14px_34px_rgba(10,37,64,0.04)]",
        compact ? "px-4 py-5" : "px-5 py-6 sm:rounded-[1.7rem] sm:px-6 sm:py-7",
      ].join(" ")}
    >
      <h3 className={["font-bold tracking-[-0.04em] text-[#2f255f]", compact ? "text-[1.3rem]" : "text-[1.55rem] sm:text-[2rem]"].join(" ")}>
        Direct Contact
      </h3>
      <div className={["space-y-5", compact ? "mt-6" : "mt-8 space-y-6"].join(" ")}>
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
            <div className="mt-1 break-all text-[0.98rem] font-semibold text-[#2f255f] sm:text-[1.1rem]">
              contact@tregocapital.com
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ContactOfficesCard({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={[
        "rounded-[1.5rem] border border-[#ece2e6] bg-white shadow-[0_14px_34px_rgba(10,37,64,0.04)]",
        compact ? "px-4 py-5" : "px-5 py-6 sm:rounded-[1.7rem] sm:px-6 sm:py-7",
      ].join(" ")}
    >
      <h3 className={["font-bold tracking-[-0.04em] text-[#2f255f]", compact ? "text-[1.3rem]" : "text-[1.55rem] sm:text-[2rem]"].join(" ")}>
        Our Offices
      </h3>
      <div className={compact ? "mt-6" : "mt-8"}>
        <OfficeAccordionList variant={compact ? "footer" : "full"} />
      </div>
    </div>
  );
}

export function ContactSidePanel() {
  return (
    <div className="space-y-5 sm:space-y-6">
      <ContactDirectCard />
      <ContactOfficesCard />
    </div>
  );
}

export function ResponsiveContactPanels() {
  const [activeTab, setActiveTab] = useState<ContactTab>("inquiry");

  return (
    <>
      <div className="lg:hidden">
        <div className="rounded-[1.3rem] border border-[#ece2e6] bg-white p-2 shadow-[0_12px_28px_rgba(10,37,64,0.04)]">
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: "inquiry", label: "Inquiry" },
              { id: "contact", label: "Contact" },
              { id: "offices", label: "Offices" },
            ].map((tab) => {
              const isActive = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id as ContactTab)}
                  className={[
                    "interactive-press rounded-[0.95rem] px-3 py-3 text-[0.7rem] font-semibold uppercase tracking-[0.12em] transition",
                    isActive
                      ? "border border-[#7f3922] bg-[#853921] text-white shadow-[0_10px_18px_rgba(133,57,33,0.18)]"
                      : "border border-[#ece2e6] bg-[#fcfaf8] text-[#66788c]",
                  ].join(" ")}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-4">
          {activeTab === "inquiry" && <ContactFormPanel compact />}
          {activeTab === "contact" && <ContactDirectCard compact />}
          {activeTab === "offices" && <ContactOfficesCard compact />}
        </div>
      </div>

      <div className="hidden gap-8 lg:grid lg:grid-cols-[1.18fr_0.82fr]">
        <ContactFormPanel />
        <ContactSidePanel />
      </div>
    </>
  );
}
