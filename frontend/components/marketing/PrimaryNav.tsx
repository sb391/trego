"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { BrandLogo } from "./BrandLogo";
import { serviceCards } from "./site-data";

const navLinks = [
  { href: "/about", label: "About" },
  { href: "/services", label: "Services" },
  { href: "/capabilities", label: "Capabilities" },
  { href: "/approach", label: "Approach" },
];

export function PrimaryNav() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const warmRoutes = Array.from(
      new Set([
        "/",
        "/about",
        "/services",
        "/capabilities",
        "/approach",
        "/contact",
        "/speak-to-advisor",
        ...serviceCards.map((service) => `/services/${service.slug}`),
      ]),
    );

    warmRoutes.forEach((route) => router.prefetch(route));
  }, [router]);

  return (
    <header className="sticky top-0 z-50 border-b border-[#ece2e6] bg-[rgba(255,253,250,0.96)] backdrop-blur-xl shadow-[0_12px_30px_rgba(10,37,64,0.12)]">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-8 sm:py-4 lg:px-12">
        <BrandLogo />

        <nav className="hidden items-center gap-8 lg:flex">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="interactive-press text-[0.9rem] font-semibold uppercase tracking-[0.06em] text-[#24124d] transition hover:text-[#8d3f28]"
            >
              {link.label}
            </Link>
          ))}
          <Link
            href="/speak-to-advisor"
            className="interactive-press inline-flex min-w-[188px] items-center justify-center rounded-[0.9rem] border border-[#7f3922] bg-[#853921] px-6 py-3 text-[0.78rem] font-semibold uppercase tracking-[0.09em] text-white shadow-[0_14px_24px_rgba(133,57,33,0.28)] transition hover:bg-[#73301b] hover:shadow-[0_18px_30px_rgba(115,48,27,0.32)]"
          >
            Speak to Advisor
          </Link>
        </nav>

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="interactive-press inline-flex items-center justify-center rounded-full border border-[#e4d7de] bg-white p-2.5 text-[#30146f] shadow-[0_10px_20px_rgba(10,37,64,0.04)] lg:hidden"
          aria-label="Toggle navigation"
          aria-expanded={open}
        >
          <span className="block h-3 w-5">
            <span className="block h-0.5 w-5 bg-current" />
            <span className="mt-1.5 block h-0.5 w-5 bg-current" />
            <span className="mt-1.5 block h-0.5 w-5 bg-current" />
          </span>
        </button>
      </div>

      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden border-t border-[#ece2e6] bg-white lg:hidden"
          >
            <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-4 sm:px-8">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="interactive-press rounded-2xl px-4 py-3.5 text-[0.82rem] font-semibold uppercase tracking-[0.08em] text-[#4f6276] transition hover:bg-[#faf7f3] hover:text-[#30146f]"
                  onClick={() => setOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
              <Link
                href="/speak-to-advisor"
                className="interactive-press mt-2 rounded-[0.9rem] border border-[#7f3922] bg-[#853921] px-4 py-3.5 text-center text-[0.78rem] font-semibold uppercase tracking-[0.09em] text-white shadow-[0_14px_24px_rgba(133,57,33,0.22)]"
                onClick={() => setOpen(false)}
              >
                Speak to Advisor
              </Link>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
