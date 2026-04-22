import Link from "next/link";
import Image from "next/image";

import { HeroValueIllustration } from "../components/marketing/HeroValueIllustration";
import { MarketingShell } from "../components/marketing/MarketingShell";
import { Reveal } from "../components/marketing/Reveal";
import { agencyLinks, serviceCards } from "../components/marketing/site-data";

const heroStats = [
  { value: "₹5,000+ Cr", label: "Credit enabled" },
  { value: "7", label: "Agencies covered" },
  { value: "10+", label: "Capital channels" },
];

const tapeItems = [
  "₹5,000+ Cr Capital Enabled",
  "100+ Corporate Assessments",
  "7 Rating Agencies Covered",
  "10+ Capital Channels Activated",
  "Simulation before agency meetings",
  "Advisory before lender review",
];

const processFlow = [
  { title: "Share financials", note: "Current numbers and working-capital posture" },
  { title: "See likely direction", note: "Agency-wise interpretation and risk signals" },
  { title: "Tighten readiness", note: "Documentation, management, and narrative" },
  { title: "Enter discussions clearer", note: "Lenders, agencies, or TReDS conversations" },
];

const tapeLoop = [...tapeItems, ...tapeItems];

export default function HomePage() {
  return (
    <MarketingShell>
      <section className="relative overflow-hidden border-b border-[#ece2e6] bg-[linear-gradient(180deg,#faf6f0_0%,#fcfaf6_100%)] pt-10 sm:pt-14 lg:pt-14">
        <div className="pointer-events-none absolute inset-0 z-0 hero-wash opacity-58" />
        <div className="pointer-events-none absolute inset-0 z-0 soft-grid opacity-[0.09]" />

        <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-8 lg:px-12">
          <div className="grid items-center gap-6 py-2 sm:gap-8 sm:py-3 lg:grid-cols-[0.88fr_1.12fr] lg:gap-10 lg:py-4">
            <div className="max-w-[35rem]">
              <Reveal y={16}>
                <div className="inline-flex items-center gap-3 rounded-full border border-[#d7bcb0] bg-white px-4 py-2 text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-[#8c4429] shadow-[0_12px_24px_rgba(10,37,64,0.05)] sm:px-5 sm:py-2.5 sm:text-[0.74rem] sm:tracking-[0.24em]">
                  <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[#a4caa5]" />
                  Institutional Credit Advisory
                </div>
              </Reveal>

              <Reveal delay={0.06} y={20}>
                <h1 className="mt-5 max-w-[13.6ch] text-[1.7rem] font-black leading-[0.97] tracking-[-0.06em] text-[#34186f] sm:mt-6 sm:max-w-[14.2ch] sm:text-[2.38rem] lg:text-[2.82rem]">
                  <span className="block">See your credit</span>
                  <span className="block">position</span>
                  <span className="block italic text-[#7a3727] lg:whitespace-nowrap">before the market does.</span>
                </h1>
              </Reveal>

              <Reveal delay={0.12} y={18}>
                <p className="mt-5 max-w-[31rem] text-[0.9rem] leading-[1.8] text-[#6d7d8f] sm:mt-6 sm:text-[0.98rem] sm:leading-[2]">
                  TreGo Capital helps corporates simulate rating direction, improve readiness, and enter capital
                  conversations with more control.
                </p>
              </Reveal>

              <Reveal delay={0.18} y={16}>
                <div className="mt-6 flex flex-col gap-3 sm:mt-7 sm:flex-row sm:items-center sm:gap-4">
                  <Link
                    href="/speak-to-advisor"
                    className="interactive-press inline-flex min-w-[164px] items-center justify-center rounded-[0.92rem] border border-[#7f3922] bg-[#853921] px-5 py-3 text-[0.72rem] font-semibold uppercase tracking-[0.08em] text-white shadow-[0_14px_24px_rgba(133,57,33,0.28)] transition hover:bg-[#73301b] hover:shadow-[0_18px_30px_rgba(115,48,27,0.32)] sm:min-w-[186px] sm:px-6 sm:py-3.5 sm:text-[0.77rem] sm:tracking-[0.09em]"
                  >
                    Speak to Advisor
                  </Link>
                  <Link
                    href="/services"
                    className="interactive-press inline-flex min-w-[164px] items-center justify-center rounded-[0.92rem] border border-[#b7a7c2] bg-white px-5 py-3 text-[0.72rem] font-semibold uppercase tracking-[0.08em] text-[#30146f] shadow-[0_10px_18px_rgba(10,37,64,0.05)] transition hover:border-[#a993ba] hover:bg-[#fffbf8] sm:min-w-[186px] sm:px-6 sm:py-3.5 sm:text-[0.77rem] sm:tracking-[0.09em]"
                  >
                    Explore Services
                  </Link>
                </div>
              </Reveal>

              <Reveal delay={0.24} y={16}>
                <div className="mt-7 max-w-[37rem] overflow-hidden rounded-[1.2rem] border border-[#ebe1df] bg-white/96 shadow-[0_12px_24px_rgba(10,37,64,0.045)] sm:mt-10 sm:max-w-[38rem] lg:max-w-[39rem]">
                  <div className="grid grid-cols-3 bg-white">
                    {heroStats.map((stat) => (
                      <div
                        key={stat.label}
                        className="border-r border-[#ebe1df] px-3 py-2.5 last:border-r-0 sm:px-7 sm:py-[1.05rem]"
                      >
                        <div className="whitespace-nowrap text-[0.84rem] font-extrabold leading-none tracking-[-0.05em] text-[#2d1870] sm:text-[1.14rem] lg:text-[1.22rem]">
                          {stat.value}
                        </div>
                        <div className="mt-1.5 whitespace-nowrap text-[0.44rem] font-medium uppercase tracking-[0.12em] text-[#9aa7b6] sm:text-[0.56rem] sm:tracking-[0.18em]">
                          {stat.label}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </Reveal>
            </div>

            <Reveal delay={0.16} y={24}>
              <HeroValueIllustration />
            </Reveal>
          </div>
        </div>

        <div className="mt-10 border-y border-[#eee3df] bg-white/86 sm:mt-8">
          <div className="ticker-shell py-3">
            <div className="ticker-track-light px-6">
              {tapeLoop.map((item, index) => (
                <div
                  key={`${item}-${index}`}
                  className="flex min-w-fit items-center gap-3 text-[0.71rem] font-semibold uppercase tracking-[0.16em] text-[#c9bcc1]"
                >
                  <span className="text-[#d2c4c9]">✦</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="bg-white py-12 sm:py-18 lg:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-8 lg:px-12">
          <Reveal>
            <div className="max-w-2xl">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.32em] text-[#b86140]">Core focus areas</p>
              <h2 className="mt-4 max-w-[13ch] text-[1.52rem] font-extrabold leading-[1.05] tracking-[-0.05em] text-[#2d1870] sm:text-[1.95rem] lg:text-[2.1rem]">
                Four clean tracks. One stronger capital position.
              </h2>
              <p className="mt-4 max-w-lg text-[0.94rem] leading-7 text-[#69798b]">
                A smaller set of services, each designed to improve capital readiness before external interpretation
                begins.
              </p>
            </div>
          </Reveal>

          <div className="mt-7 grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-2 xl:grid-cols-4">
            {serviceCards.map((card, index) => (
              <Reveal key={card.slug} delay={index * 0.04}>
                <Link
                  href={`/services/${card.slug}`}
                  className={[
                    "flex min-h-[11.75rem] flex-col rounded-[1.25rem] border px-4 py-4 shadow-[0_16px_34px_rgba(10,37,64,0.04)] transition hover:-translate-y-1 sm:min-h-[15rem] sm:rounded-[1.55rem] sm:px-6 sm:py-6",
                    index % 2 === 1
                      ? "border-[#1b2048] bg-[linear-gradient(135deg,#151c43_0%,#241b52_100%)] text-white"
                      : "border-[#ece2e6] bg-[linear-gradient(180deg,#ffffff_0%,#fbf8f4_100%)] text-[#1a1d36]",
                  ].join(" ")}
                >
                  <div
                    className={[
                      "inline-flex w-fit rounded-full px-3 py-1.5 text-[0.56rem] font-semibold uppercase tracking-[0.16em] sm:px-4 sm:py-2 sm:text-[0.68rem] sm:tracking-[0.22em]",
                      index % 2 === 1
                        ? "border border-white/14 bg-white/6 text-[#f0dec8]"
                        : "border border-[#eadde1] bg-white text-[#b86140]",
                    ].join(" ")}
                  >
                    {card.tag}
                  </div>
                  <h3 className="mt-4 max-w-[10ch] text-[0.94rem] font-bold leading-[1.12] tracking-[-0.04em] sm:mt-5 sm:max-w-[12ch] sm:text-[1.2rem]">
                    {card.title}
                  </h3>
                  <p
                    className={[
                      "mt-2 line-clamp-4 text-[0.76rem] leading-5 sm:mt-4 sm:line-clamp-none sm:text-[0.92rem] sm:leading-7",
                      index % 2 === 1 ? "text-white/76" : "text-[#66788c]",
                    ].join(" ")}
                  >
                    {card.summary}
                  </p>
                  <div
                    className={[
                      "mt-auto pt-3 text-[0.64rem] font-semibold uppercase tracking-[0.16em] sm:pt-5 sm:text-[0.72rem] sm:tracking-[0.22em]",
                      index % 2 === 1 ? "text-[#f0dec8]" : "text-[#b86140]",
                    ].join(" ")}
                  >
                    <span className="sm:hidden">Read more</span>
                    <span className="hidden sm:inline">View service</span>
                  </div>
                </Link>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[linear-gradient(180deg,#f9f4ed_0%,#f7f2ea_100%)] py-12 sm:py-18">
        <div className="mx-auto max-w-7xl px-4 sm:px-8 lg:px-12">
          <Reveal>
            <div className="grid gap-10 lg:grid-cols-[0.82fr_1.18fr] lg:items-center">
              <div className="max-w-xl">
                <p className="text-[0.72rem] font-semibold uppercase tracking-[0.32em] text-[#b86140]">Approach</p>
                <h2 className="mt-4 max-w-[14ch] text-[1.56rem] font-extrabold leading-[1.05] tracking-[-0.05em] text-[#2d1870] sm:text-[2rem] lg:text-[2.15rem]">
                  Less noise. A clearer path from numbers to capital decisions.
                </h2>
                <p className="mt-4 text-[0.95rem] leading-7 text-[#69798b]">
                  TreGo is designed to reduce uncertainty before lenders, agencies, or TReDS platforms frame their own
                  first view.
                </p>
              </div>

              <div className="rounded-[1.55rem] border border-[#ece1e4] bg-white px-5 py-6 shadow-[0_18px_40px_rgba(10,37,64,0.05)] sm:rounded-[1.85rem] sm:px-6 sm:py-7">
                <div className="relative grid grid-cols-2 gap-5 sm:grid-cols-4 sm:gap-4">
                  <div className="absolute left-[8%] right-[8%] top-[1.6rem] hidden h-px bg-gradient-to-r from-[#ead2c7] via-[#d8c6ea] to-[#b86140] sm:block" />
                  {processFlow.map((item, index) => (
                    <div key={item.title} className="relative">
                      <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#f5eeea] text-[0.82rem] font-semibold text-[#b86140]">
                        0{index + 1}
                      </div>
                      <div className="mt-4 text-[0.98rem] font-semibold text-[#231f49]">{item.title}</div>
                      <div className="mt-2 text-[0.88rem] leading-6 text-[#738396]">{item.note}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="bg-[#171a3a] py-12 text-white sm:py-14">
        <div className="mx-auto max-w-7xl px-4 sm:px-8 lg:px-12">
          <Reveal>
            <div className="grid gap-8 lg:grid-cols-[0.82fr_1.18fr] lg:items-center">
              <div className="max-w-lg">
                <p className="text-[0.72rem] font-semibold uppercase tracking-[0.32em] text-[#f0d8bf]">Agency coverage</p>
                <h2 className="mt-4 text-[1.56rem] font-extrabold leading-[1.06] tracking-[-0.04em] text-white sm:text-[2.05rem]">
                  Built around the agency frameworks that matter in India.
                </h2>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {agencyLinks.map((agency) => (
                  <a
                    key={agency.label}
                    href={agency.href}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-[1rem] border border-white/10 bg-white/[0.04] px-4 py-4 text-center transition hover:border-white/20 hover:bg-white/[0.07]"
                  >
                    <div className="text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-white/88">{agency.label}</div>
                  </a>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="bg-[linear-gradient(180deg,#f8f2ea_0%,#f4eee6_100%)] py-12 sm:py-18">
        <div className="mx-auto max-w-7xl px-4 sm:px-8 lg:px-12">
          <Reveal>
            <div className="rounded-[1.65rem] border border-[#ece2e6] bg-white px-5 py-5 shadow-[0_18px_42px_rgba(10,37,64,0.05)] sm:rounded-[1.9rem] sm:px-10 sm:py-8 lg:px-12">
              <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
                <div className="max-w-xl">
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.32em] text-[#b86140]">Start with TreGo</p>
                  <h2 className="mt-4 max-w-[13ch] text-[1.58rem] font-extrabold leading-[1.05] tracking-[-0.05em] text-[#2d1870] sm:text-[2.1rem]">
                    Know where the business stands before the market decides for you.
                  </h2>
                  <p className="mt-4 text-[0.92rem] leading-7 text-[#69798b] sm:text-[0.95rem]">
                    We help management teams, CFOs, and advisors move into capital conversations with more control.
                  </p>

                  <div className="mt-6 flex flex-col gap-3 sm:mt-7 sm:flex-row sm:gap-4">
                    <Link
                      href="/speak-to-advisor"
                      className="interactive-press inline-flex items-center justify-center rounded-[0.92rem] bg-[#92442b] px-6 py-3.5 text-[0.78rem] font-semibold text-white shadow-[0_16px_28px_rgba(146,68,43,0.26)] transition hover:bg-[#7e3721] sm:px-7 sm:text-[0.84rem]"
                    >
                      Speak to Advisor
                    </Link>
                    <Link
                      href="/services"
                      className="interactive-press inline-flex items-center justify-center rounded-[0.92rem] border-2 border-[#d8cdd5] bg-white px-6 py-3.5 text-[0.78rem] font-semibold text-[#2f255f] transition hover:border-[#c9bec7] sm:px-7 sm:text-[0.84rem]"
                    >
                      Explore Services
                    </Link>
                  </div>
                </div>

                <TregoMeaningIllustration />
              </div>
            </div>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}

function TregoMeaningIllustration() {
  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-x-[8%] top-[14%] h-[70%] rounded-[2.5rem] bg-[radial-gradient(circle_at_center,rgba(232,214,255,0.34),transparent_72%)] blur-3xl" />
      <div className="pointer-events-none absolute left-[10%] top-[38%] h-28 w-28 rounded-full bg-[radial-gradient(circle,rgba(88,192,198,0.24),transparent_70%)] blur-2xl" />
      <div className="pointer-events-none absolute right-[12%] top-[28%] h-24 w-24 rounded-full bg-[radial-gradient(circle,rgba(207,167,110,0.22),transparent_70%)] blur-2xl" />

      <div className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 z-10 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.64),transparent_30%)]" />
        <Image
          src="/assets/process-flow.avif"
          alt="TreGo process flow illustration"
          width={1280}
          height={960}
          sizes="(min-width: 1280px) 50vw, (min-width: 1024px) 48vw, 92vw"
          className="relative z-0 h-auto w-full object-contain"
          style={{
            filter: "drop-shadow(0 24px 36px rgba(31, 24, 61, 0.08))",
            WebkitMaskImage:
              "radial-gradient(circle at center, rgba(0,0,0,1) 58%, rgba(0,0,0,0.88) 76%, rgba(0,0,0,0.38) 90%, rgba(0,0,0,0) 100%)",
            maskImage:
              "radial-gradient(circle at center, rgba(0,0,0,1) 58%, rgba(0,0,0,0.88) 76%, rgba(0,0,0,0.38) 90%, rgba(0,0,0,0) 100%)",
          }}
        />
      </div>
    </div>
  );
}
