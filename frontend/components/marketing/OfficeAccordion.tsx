"use client";

import { useState } from "react";

export const officeLocations = [
  {
    city: "Gurgaon",
    address: "B-2901, Emaar Digihomes, Golf Course Extension Road, Sector-62, Gurugram, Haryana - 122102",
    phone: "+91-7506429193",
  },
  {
    city: "Mumbai",
    address: "Flat 507, Wing A Raheja Residency, Film City Road, Malad East, Mumbai, Maharashtra - 400097",
    phone: "+91-9819980978",
  },
] as const;

type OfficeCity = (typeof officeLocations)[number]["city"];

export function OfficeAccordionList({ variant = "full" }: { variant?: "full" | "footer" }) {
  const [openCity, setOpenCity] = useState<OfficeCity | null>(null);
  const isFooter = variant === "footer";

  return (
    <div className={isFooter ? "space-y-3" : "space-y-3.5 sm:space-y-4"}>
      {officeLocations.map((office) => {
        const isOpen = openCity === office.city;
        const phoneHref = `tel:${office.phone.replace(/[^+\d]/g, "")}`;

        return (
          <div
            key={office.city}
            onMouseLeave={() => setOpenCity(null)}
            className={[
              "overflow-hidden rounded-[1.35rem] border bg-[linear-gradient(180deg,#ffffff_0%,#fdfaf7_100%)] transition-all duration-300",
              isOpen
                ? "border-[#e7d6dc] shadow-[0_18px_34px_rgba(24,32,57,0.06)]"
                : "border-[#f0e7e9] shadow-[0_8px_18px_rgba(24,32,57,0.03)] hover:border-[#e8dadf]",
            ].join(" ")}
          >
            <button
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpenCity((current) => (current === office.city ? null : office.city))}
              onMouseEnter={() => setOpenCity(office.city)}
              className={[
                "flex w-full items-center justify-between gap-4 text-left",
                isFooter ? "px-4 py-3.5" : "px-4 py-3.5 sm:px-6 sm:py-4",
              ].join(" ")}
            >
              <div className="flex min-w-0 items-center gap-4">
                <div
                  className={[
                    "flex shrink-0 items-center justify-center rounded-full bg-[#f8efed] text-[#b45a3c]",
                    isFooter ? "h-10 w-10" : "h-11 w-11",
                  ].join(" ")}
                >
                  <LocationPinIcon />
                </div>
                <div className="min-w-0">
                  <div
                    className={[
                      "font-semibold tracking-[-0.03em] text-[#26203f]",
                      isFooter ? "text-[1.05rem]" : "text-[1.08rem] sm:text-[1.28rem]",
                    ].join(" ")}
                  >
                    {office.city}
                  </div>
                </div>
              </div>

              <div
                className={[
                  "flex shrink-0 items-center justify-center rounded-full border transition-all duration-300",
                  isOpen
                    ? "border-[#d8c5cb] bg-[#fbf4f2] text-[#8f4027]"
                    : "border-[#ece2e6] bg-white text-[#9caaba]",
                  isFooter ? "h-9 w-9" : "h-10 w-10",
                ].join(" ")}
              >
                <ChevronIcon open={isOpen} />
              </div>
            </button>

            <div
              className={[
                "grid transition-all duration-300 ease-out",
                isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
              ].join(" ")}
            >
              <div className="overflow-hidden">
                <div
                  className={[
                    "border-t border-[#f1e6e8]",
                    isFooter ? "px-4 pb-4 pt-1" : "px-4 pb-4 pt-1 sm:px-6 sm:pb-5",
                  ].join(" ")}
                >
                  <div className={isFooter ? "pl-[3.25rem]" : "pl-[3.45rem] sm:pl-[3.75rem]"}>
                    <p
                      className={[
                        "text-[#607187]",
                        isFooter ? "max-w-[21rem] text-[0.92rem] leading-7" : "max-w-[26rem] text-[0.92rem] leading-7 sm:text-[1rem] sm:leading-9",
                      ].join(" ")}
                    >
                      {office.address}
                    </p>

                    <div className="mt-4 flex flex-wrap items-center gap-3">
                      <a
                        href={phoneHref}
                        className={[
                          "inline-flex items-center gap-2 rounded-full border border-[#ead7dc] bg-white font-semibold text-[#2f255f] shadow-[0_8px_18px_rgba(24,32,57,0.04)] transition hover:border-[#dcc6cc] hover:bg-[#fffaf8]",
                          isFooter ? "px-3.5 py-2 text-[0.82rem]" : "px-3.5 py-2 text-[0.82rem] sm:px-4 sm:text-[0.9rem]",
                        ].join(" ")}
                      >
                        <PhoneIcon />
                        {office.phone}
                      </a>
                      <a
                        href={phoneHref}
                        className={[
                          "inline-flex items-center rounded-full bg-[#853921] font-semibold uppercase tracking-[0.08em] text-white shadow-[0_12px_22px_rgba(133,57,33,0.22)] transition hover:bg-[#73301b]",
                          isFooter ? "px-3.5 py-2 text-[0.72rem]" : "px-3.5 py-2 text-[0.72rem] sm:px-4 sm:text-[0.82rem]",
                        ].join(" ")}
                      >
                        Call
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LocationPinIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
      <path d="M12 21s6-5.73 6-11a6 6 0 1 0-12 0c0 5.27 6 11 6 11Z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 text-[#b45a3c]" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.9.33 1.77.63 2.6a2 2 0 0 1-.45 2.11L8 9.73a16 16 0 0 0 6.27 6.27l1.3-1.29a2 2 0 0 1 2.11-.45c.83.3 1.7.51 2.6.63A2 2 0 0 1 22 16.92Z" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={["h-4 w-4 transition-transform duration-300", open ? "rotate-180" : ""].join(" ")}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
