import type { ReactNode } from "react";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";

import { MarketingShell } from "../../../components/marketing/MarketingShell";
import { serviceCards } from "../../../components/marketing/site-data";

type Params = {
  slug: string;
};

type Service = (typeof serviceCards)[number];

export function generateStaticParams() {
  return serviceCards.map((service) => ({ slug: service.slug }));
}

export default async function ServiceDetailPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const service = serviceCards.find((item) => item.slug === slug);

  if (!service) {
    notFound();
  }

  return (
    <MarketingShell>
      <section className="bg-[linear-gradient(180deg,#f4eef9_0%,#fbf8f4_100%)] py-14 sm:py-18 lg:py-20">
        <div className="mx-auto max-w-7xl px-4 text-center sm:px-8 lg:px-12">
          <div className="inline-flex items-center gap-3 rounded-full border border-[#e3d4dc] bg-white/88 px-4 py-2 text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-[#b55342] shadow-[0_10px_26px_rgba(41,20,95,0.06)] sm:px-5 sm:py-2.5 sm:text-[0.72rem] sm:tracking-[0.24em]">
            <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[#b55342]" />
            {service.heroEyebrow}
          </div>
          <h1 className="mx-auto mt-5 max-w-4xl text-[1.75rem] font-extrabold leading-[1.04] tracking-[-0.05em] text-[#29145f] sm:mt-6 sm:text-[2.7rem] lg:text-[3.2rem]">
            {service.title}
          </h1>
          <p className="mx-auto mt-4 max-w-3xl text-[0.92rem] leading-7 text-[#5f7085] sm:mt-5 sm:text-[1.03rem] sm:leading-8">
            {service.description}
          </p>
        </div>
      </section>

      <section className="bg-[#fffdfa] py-14 sm:py-18 lg:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-8 lg:px-12">
          <div className="grid gap-10 lg:grid-cols-[0.88fr_1.12fr] lg:items-center lg:gap-12">
            <div className="max-w-2xl">
              <div className="inline-flex items-center gap-4 text-[0.74rem] font-semibold uppercase tracking-[0.34em] text-[#b55342]">
                <span className="h-px w-10 bg-[#b55342]" />
                Deep Dive
              </div>

              <h2 className="mt-6 text-[1.68rem] font-extrabold leading-[1.06] tracking-[-0.05em] text-[#2a1563] sm:mt-7 sm:text-[2.5rem] lg:text-[2.95rem]">
                {service.overviewTitle}{" "}
                <span className="font-medium italic text-[#b24949]">{service.overviewAccent}</span>
              </h2>

              {service.overviewParagraphs.map((paragraph) => (
                <p key={paragraph} className="mt-5 text-[0.95rem] leading-7 text-[#5a6b82] sm:mt-6 sm:text-[1.03rem] sm:leading-9">
                  {paragraph}
                </p>
              ))}

              <div className="mt-8 grid gap-4 sm:grid-cols-2">
                {service.detailPoints.map((point) => (
                  <div
                    key={point}
                    className="rounded-[1.15rem] border border-[#ece1e6] bg-[#fffdfa] px-4 py-4 text-[0.9rem] leading-6 text-[#4f6279] shadow-[0_14px_28px_rgba(25,20,61,0.04)] sm:rounded-[1.3rem] sm:px-5 sm:text-[0.95rem] sm:leading-7"
                  >
                    <span className="mb-3 inline-flex h-2.5 w-2.5 rounded-full bg-[#b55342]" />
                    <div>{point}</div>
                  </div>
                ))}
              </div>

              <div className="mt-7 flex flex-col gap-3 sm:mt-8 sm:flex-row">
                <Link
                  href="/speak-to-advisor"
                  className="interactive-press inline-flex items-center justify-center rounded-full bg-[#a84c2e] px-6 py-3.5 text-[0.9rem] font-semibold text-white shadow-[0_16px_28px_rgba(168,76,46,0.24)] transition hover:bg-[#963f25] sm:px-7 sm:py-4 sm:text-sm"
                >
                  Speak to Advisor
                </Link>
                <Link
                  href="/services"
                  className="interactive-press inline-flex items-center justify-center rounded-full border-2 border-[#dbcfda] bg-white px-6 py-3.5 text-[0.9rem] font-semibold text-[#2a1563] transition hover:border-[#cfc2cf] sm:px-7 sm:py-4 sm:text-sm"
                >
                  Explore Services
                </Link>
              </div>
            </div>

            <ServicePoster service={service} />
          </div>
        </div>
      </section>

      <section className="bg-[linear-gradient(180deg,#f9f5f0_0%,#fffdfa_100%)] py-14 sm:py-18 lg:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-8 lg:px-12">
          <div className="max-w-3xl">
            <div className="text-[0.74rem] font-semibold uppercase tracking-[0.32em] text-[#b55342]">
              Why It Matters
            </div>
            <h3 className="mt-4 text-[1.65rem] font-extrabold leading-[1.06] tracking-[-0.05em] text-[#29145f] sm:text-[2.25rem]">
              What this service improves for the business.
            </h3>
            <p className="mt-4 text-[0.92rem] leading-7 text-[#5f7085] sm:text-[0.98rem] sm:leading-8">
              Each TreGo service is meant to create a better institutional response, not just a prettier process.
            </p>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {service.businessImpact.map((item, index) => (
              <div
                key={item.title}
                className="rounded-[1.35rem] border border-[#ece1e6] bg-white px-5 py-5 shadow-[0_14px_30px_rgba(25,20,61,0.04)] sm:rounded-[1.55rem] sm:px-6 sm:py-6"
              >
                <div className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-[#f8efea] text-[0.8rem] font-semibold text-[#b55342]">
                  0{index + 1}
                </div>
                <h4 className="mt-4 text-[1rem] font-bold leading-7 text-[#241c44] sm:mt-5 sm:text-[1.08rem]">{item.title}</h4>
                <p className="mt-3 text-[0.9rem] leading-7 text-[#61728a] sm:text-[0.94rem]">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}

function ServicePoster({ service }: { service: Service }) {
  return (
    <div className="relative mx-auto w-full max-w-[34rem] lg:max-w-none lg:pl-2">
      <div className="pointer-events-none absolute inset-x-[8%] top-[10%] h-[74%] rounded-[3rem] bg-[radial-gradient(circle_at_center,rgba(236,220,255,0.32),transparent_72%)] blur-3xl" />
      <div className="pointer-events-none absolute right-[8%] top-[16%] h-28 w-28 rounded-full bg-[radial-gradient(circle,rgba(255,219,170,0.20),transparent_70%)] blur-2xl" />

      <div className="relative">
        <div className="pointer-events-none absolute inset-0 z-10 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.58),transparent_30%)]" />
        <Image
          src={service.visual}
          alt={`${service.title} illustration`}
          width={1024}
          height={1536}
          sizes="(min-width: 1280px) 48vw, (min-width: 1024px) 46vw, 92vw"
          className="relative z-0 h-auto w-full object-contain"
          style={{
            filter: "drop-shadow(0 26px 40px rgba(28, 21, 61, 0.08))",
            WebkitMaskImage:
              "radial-gradient(circle at center, rgba(0,0,0,1) 60%, rgba(0,0,0,0.92) 76%, rgba(0,0,0,0.44) 90%, rgba(0,0,0,0) 100%)",
            maskImage:
              "radial-gradient(circle at center, rgba(0,0,0,1) 60%, rgba(0,0,0,0.92) 76%, rgba(0,0,0,0.44) 90%, rgba(0,0,0,0) 100%)",
          }}
        />
      </div>

      <div className="mt-4 max-w-[32rem] px-1.5 sm:px-2">
        <div className="text-[0.76rem] font-semibold uppercase tracking-[0.26em] text-[#b86140]">TreGo insight</div>
        <div className="mt-2 text-[1rem] font-bold text-[#241c44] sm:text-[1.12rem]">{service.calloutTitle}</div>
        <p className="mt-2 text-[0.9rem] leading-7 text-[#627289] sm:text-[0.92rem]">{service.calloutCopy}</p>
      </div>
    </div>
  );
}

function SimulationPoster() {
  return (
    <PosterCanvas eyebrow="Rating engine pipeline" tone="light">
      <svg viewBox="0 0 720 360" className="h-[16.5rem] w-full sm:h-[18.5rem]" aria-hidden="true">
        <defs>
          <linearGradient id="simBeam" x1="0%" y1="50%" x2="100%" y2="50%">
            <stop offset="0%" stopColor="#f5dfbb" stopOpacity="0" />
            <stop offset="50%" stopColor="#f4d49c" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#f5dfbb" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="simMetal" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6b7385" />
            <stop offset="100%" stopColor="#2e3346" />
          </linearGradient>
          <linearGradient id="simPanel" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#f8f2ea" />
          </linearGradient>
          <filter id="simShadow" x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow dx="0" dy="14" stdDeviation="18" floodColor="#28185f" floodOpacity="0.1" />
          </filter>
          <radialGradient id="simGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff0c7" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#fff0c7" stopOpacity="0" />
          </radialGradient>
        </defs>
        <path d="M148 186 C254 186, 290 154, 360 154 S484 204, 596 204" stroke="url(#simBeam)" strokeWidth="8" fill="none" strokeLinecap="round">
          <animate attributeName="opacity" values="0.45;1;0.45" dur="4.2s" repeatCount="indefinite" />
        </path>
        <path d="M124 200 C248 200, 290 170, 360 170 S486 216, 620 216" stroke="url(#simBeam)" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.7">
          <animate attributeName="opacity" values="0.15;0.7;0.15" dur="5.1s" repeatCount="indefinite" />
        </path>

        <g transform="translate(56 88)" filter="url(#simShadow)">
          <animateTransform attributeName="transform" type="translate" values="56 88;56 82;56 88" dur="6s" repeatCount="indefinite" />
          <path d="M8 30 L116 6 L132 102 L24 126 Z" fill="url(#simPanel)" stroke="#e6d9dd" />
          <path d="M30 42 L138 18 L154 114 L46 138 Z" fill="#ffffff" stroke="#e6d9dd" />
          <path d="M52 54 L160 30 L176 126 L68 150 Z" fill="#fffdfa" stroke="#e6d9dd" />
          <circle cx="128" cy="56" r="11" fill="#edc982" />
          <rect x="74" y="78" width="60" height="6" rx="3" fill="#ddd1e2" />
          <rect x="74" y="92" width="48" height="6" rx="3" fill="#e9dfd4" />
          <rect x="74" y="106" width="70" height="6" rx="3" fill="#ddd1e2" />
        </g>

        <g transform="translate(246 82)" filter="url(#simShadow)">
          <animateTransform attributeName="transform" type="translate" values="246 82;246 76;246 82" dur="5.4s" repeatCount="indefinite" />
          <ellipse cx="116" cy="142" rx="124" ry="34" fill="url(#simGlow)" />
          <ellipse cx="116" cy="138" rx="98" ry="26" fill="url(#simMetal)" />
          <ellipse cx="116" cy="130" rx="74" ry="20" fill="#efe7da" />
          <ellipse cx="116" cy="124" rx="46" ry="14" fill="#6b7385" />
          <circle cx="116" cy="94" r="48" fill="url(#simGlow)">
            <animate attributeName="opacity" values="0.5;1;0.5" dur="3.8s" repeatCount="indefinite" />
          </circle>
          <path d="M80 96 C92 74, 108 62, 116 46 C126 62, 140 74, 152 96" fill="none" stroke="#f1c978" strokeWidth="12" strokeLinecap="round" />
          <path d="M78 96 C92 76, 104 66, 116 52 C128 66, 142 76, 154 96" fill="none" stroke="#fff8e1" strokeWidth="4" strokeLinecap="round" opacity="0.95" />
        </g>

        <g transform="translate(520 98)" filter="url(#simShadow)">
          <animateTransform attributeName="transform" type="translate" values="520 98;520 92;520 98" dur="6.4s" repeatCount="indefinite" />
          <g transform="translate(0 16)">
            <rect width="66" height="96" rx="12" fill="#ffffff" stroke="#e6d9dd" />
            <text x="33" y="42" textAnchor="middle" fontSize="24" fontWeight="600" fill="#36435e">AA</text>
          </g>
          <g transform="translate(44 6)">
            <rect width="68" height="104" rx="12" fill="#fffdfa" stroke="#e6d9dd" />
            <text x="34" y="45" textAnchor="middle" fontSize="25" fontWeight="600" fill="#36435e">AA</text>
          </g>
          <g transform="translate(94 22)">
            <rect width="76" height="98" rx="12" fill="#2f3346" stroke="#4a5064" />
            <text x="38" y="46" textAnchor="middle" fontSize="26" fontWeight="700" fill="#edcc87">BBB</text>
          </g>
        </g>
      </svg>

      <div className="mt-4 grid gap-3 border-t border-[#e9dde2] pt-4 sm:grid-cols-4">
        {[
          ["01", "Financial Data"],
          ["02", "Adjustments"],
          ["03", "Credit Intelligence Engine"],
          ["04", "Rating Output"],
        ].map(([count, label]) => (
          <div key={label}>
            <div className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[#b86140]">{count}</div>
            <div className="mt-1 text-[0.9rem] font-semibold leading-6 text-[#2c204d]">{label}</div>
          </div>
        ))}
      </div>
    </PosterCanvas>
  );
}

function AdvisoryPoster() {
  return (
    <PosterCanvas eyebrow="Agency readiness flow" tone="light">
      <div className="grid gap-6 lg:grid-cols-[0.82fr_1.18fr] lg:items-end">
        <div className="max-w-[17rem]">
          <h4 className="text-[1.95rem] font-semibold leading-[1.02] tracking-[-0.05em] text-[#23184f]">
            Prepare the file before the meeting begins.
          </h4>
          <p className="mt-3 text-[0.94rem] leading-7 text-[#61728a]">
            Documentation, management preparation, and meeting structure should be aligned before analysts build their
            first conclusion.
          </p>
        </div>

        <svg viewBox="0 0 460 260" className="h-[13rem] w-full sm:h-[14.5rem]" aria-hidden="true">
          <defs>
            <linearGradient id="advisoryFlowScene" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#c76e4c" />
              <stop offset="100%" stopColor="#8d65c9" />
            </linearGradient>
            <filter id="advShadow" x="-40%" y="-40%" width="180%" height="180%">
              <feDropShadow dx="0" dy="12" stdDeviation="18" floodColor="#28185f" floodOpacity="0.08" />
            </filter>
          </defs>

          <path
            d="M74 176 C146 176, 162 132, 230 132 S322 178, 404 178"
            stroke="url(#advisoryFlowScene)"
            strokeWidth="6"
            fill="none"
            strokeLinecap="round"
          />

          <g transform="translate(30 110)" filter="url(#advShadow)">
            <rect width="96" height="82" rx="20" fill="#fffdfa" stroke="#e5d8df" />
            <path d="M24 18 L68 18 L78 28 L78 62 L24 62 Z" fill="#ffffff" stroke="#d9cde6" />
            <path d="M68 18 V30 H80" fill="none" stroke="#d9cde6" />
            <path d="M32 36 H68" stroke="#e8dde5" strokeWidth="4" strokeLinecap="round" />
            <path d="M32 48 H60" stroke="#eedfcf" strokeWidth="4" strokeLinecap="round" />
            <path d="M36 6 L50 6" stroke="#c68a4d" strokeWidth="4" strokeLinecap="round" />
          </g>

          <g transform="translate(170 86)" filter="url(#advShadow)">
            <ellipse cx="62" cy="116" rx="72" ry="20" fill="#f5eef9" />
            <rect x="6" y="76" width="112" height="18" rx="9" fill="#ffffff" stroke="#e5d8df" />
            <circle cx="38" cy="44" r="13" fill="#536f98" />
            <rect x="27" y="58" width="22" height="32" rx="10" fill="#536f98" />
            <circle cx="84" cy="40" r="12" fill="#9a5a85" />
            <rect x="74" y="53" width="20" height="30" rx="10" fill="#9a5a85" />
            <rect x="48" y="18" width="26" height="18" rx="5" fill="#ffffff" stroke="#d9cde6" />
            <path d="M54 26 H68" stroke="#c68a4d" strokeWidth="3" strokeLinecap="round" />
          </g>

          <g transform="translate(318 72)" filter="url(#advShadow)">
            <rect width="112" height="122" rx="24" fill="#ffffff" stroke="#e5d8df" />
            <rect x="20" y="18" width="72" height="44" rx="12" fill="#f4eef8" />
            <path d="M34 34 H78" stroke="#d6c8e6" strokeWidth="4" strokeLinecap="round" />
            <path d="M34 46 H68" stroke="#d6c8e6" strokeWidth="4" strokeLinecap="round" />
            <rect x="28" y="76" width="56" height="30" rx="15" fill="#fff8ef" stroke="#ead7b5" />
            <text x="56" y="95" textAnchor="middle" fontSize="18" fontWeight="700" fill="#8f6332">
              AA
            </text>
          </g>
        </svg>
      </div>

      <div className="mt-5 grid gap-4 border-t border-[#e9dde2] pt-4 sm:grid-cols-3">
        {[
          ["01", "Documentation", "Credit file and support pack"],
          ["02", "Management prep", "Responses and narrative"],
          ["03", "Agency meeting", "Cleaner first discussion"],
        ].map(([count, title, copy]) => (
          <div key={title}>
            <div className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[#b86140]">{count}</div>
            <div className="mt-1 text-[0.98rem] font-semibold leading-6 text-[#271c49]">{title}</div>
            <div className="mt-1 text-[0.88rem] leading-6 text-[#627289]">{copy}</div>
          </div>
        ))}
      </div>
    </PosterCanvas>
  );
}

function TredsPoster() {
  return (
    <PosterCanvas eyebrow="TReDS marketplace flow" tone="lightBlue">
      <svg viewBox="0 0 720 360" className="h-[16.5rem] w-full sm:h-[18.5rem]" aria-hidden="true">
        <defs>
          <linearGradient id="tredsBeam" x1="0%" y1="50%" x2="100%" y2="50%">
            <stop offset="0%" stopColor="#f5dfbb" stopOpacity="0" />
            <stop offset="50%" stopColor="#f4d49c" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#f5dfbb" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="tredsPlatform" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6a7488" />
            <stop offset="100%" stopColor="#2d3344" />
          </linearGradient>
          <filter id="tredsShadow" x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow dx="0" dy="14" stdDeviation="18" floodColor="#18324f" floodOpacity="0.1" />
          </filter>
          <radialGradient id="tredsGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff0c7" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#fff0c7" stopOpacity="0" />
          </radialGradient>
        </defs>
        <path d="M126 206 C234 206, 286 166, 360 166 S486 206, 610 206" stroke="url(#tredsBeam)" strokeWidth="8" fill="none" strokeLinecap="round">
          <animate attributeName="opacity" values="0.45;1;0.45" dur="4.4s" repeatCount="indefinite" />
        </path>
        <path d="M140 222 C240 222, 294 182, 360 182 S486 220, 606 220" stroke="url(#tredsBeam)" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.7">
          <animate attributeName="opacity" values="0.18;0.76;0.18" dur="5.2s" repeatCount="indefinite" />
        </path>

        <g transform="translate(42 122)" filter="url(#tredsShadow)">
          <animateTransform attributeName="transform" type="translate" values="42 122;42 116;42 122" dur="6.2s" repeatCount="indefinite" />
          <rect width="132" height="92" rx="18" fill="#ffffff" stroke="#dde6ec" />
          <text x="28" y="34" fontSize="13" fill="#6f778c">Invoice</text>
          <text x="28" y="62" fontSize="26" fontWeight="700" fill="#274463">₹50 Lac</text>
          <path d="M28 72h44" stroke="#e7d7b9" strokeWidth="4" strokeLinecap="round" />
        </g>

        <g transform="translate(236 116)" filter="url(#tredsShadow)">
          <ellipse cx="124" cy="90" rx="132" ry="36" fill="url(#tredsGlow)" />
          <ellipse cx="124" cy="86" rx="102" ry="28" fill="url(#tredsPlatform)" />
          <ellipse cx="124" cy="78" rx="74" ry="20" fill="#f2ede4" />
          <ellipse cx="124" cy="72" rx="48" ry="13" fill="#7a818f" />
          <circle cx="124" cy="46" r="46" fill="url(#tredsGlow)">
            <animate attributeName="opacity" values="0.5;1;0.5" dur="3.8s" repeatCount="indefinite" />
          </circle>
          <text x="124" y="90" textAnchor="middle" fontSize="18" fontWeight="600" fill="#ffffff">TreGo Network</text>
        </g>

        <g transform="translate(474 86)" filter="url(#tredsShadow)">
          <animateTransform attributeName="transform" type="translate" values="474 86;474 80;474 86" dur="6s" repeatCount="indefinite" />
          <g transform="translate(0 6)">
            <rect width="114" height="42" rx="12" fill="#2f3346" stroke="#575d73" />
            <text x="22" y="26" fontSize="12" fontWeight="600" fill="#ffffff">Bank A</text>
            <text x="64" y="26" fontSize="12" fill="#d8c491">₹90 Lac</text>
          </g>
          <g transform="translate(96 20)">
            <rect width="118" height="40" rx="12" fill="#6f727e" stroke="#8f93a1" />
            <text x="18" y="24" fontSize="12" fontWeight="600" fill="#ffffff">NBFC</text>
            <text x="64" y="24" fontSize="12" fill="#f2ede6">₹99 Lac</text>
          </g>
          <g transform="translate(58 78)">
            <rect width="122" height="38" rx="12" fill="#fffdfa" stroke="#e6d9dd" />
            <text x="18" y="23" fontSize="12" fontWeight="600" fill="#444f67">FinTech C</text>
            <text x="80" y="23" fontSize="12" fill="#b26b4d">₹97 Lac</text>
          </g>
        </g>

        <g transform="translate(620 194)" filter="url(#tredsShadow)">
          <path d="M10 30 C44 18, 66 6, 90 -20" fill="none" stroke="#d8a45f" strokeWidth="8" strokeLinecap="round" />
          <path d="M82 -26 l18 8 -14 14" fill="none" stroke="#d8a45f" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
          <rect x="42" y="26" width="58" height="34" rx="8" fill="#383844" />
          <ellipse cx="38" cy="40" rx="12" ry="4.5" fill="#efcf98" />
          <ellipse cx="38" cy="47" rx="12" ry="4.5" fill="#d3a860" />
          <ellipse cx="80" cy="18" rx="12" ry="4.5" fill="#efcf98" />
          <ellipse cx="80" cy="25" rx="12" ry="4.5" fill="#d3a860" />
          <ellipse cx="96" cy="42" rx="12" ry="4.5" fill="#efcf98" />
          <ellipse cx="96" cy="49" rx="12" ry="4.5" fill="#d3a860" />
        </g>
      </svg>

      <div className="mt-4 grid gap-3 border-t border-[#dfe8ef] pt-4 sm:grid-cols-3">
        {[
          ["01", "Invoice"],
          ["02", "TreGo Network"],
          ["03", "Funds Access"],
        ].map(([count, label]) => (
          <div key={label}>
            <div className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[#b86140]">{count}</div>
            <div className="mt-1 text-[0.9rem] font-semibold leading-6 text-[#284766]">{label}</div>
          </div>
        ))}
      </div>
    </PosterCanvas>
  );
}

function CapitalPoster() {
  return (
    <PosterCanvas eyebrow="Capital transformation journey" tone="light">
      <svg viewBox="0 0 720 360" className="h-[16.5rem] w-full sm:h-[18.5rem]" aria-hidden="true">
        <defs>
          <linearGradient id="capitalBeam" x1="0%" y1="50%" x2="100%" y2="50%">
            <stop offset="0%" stopColor="#f5dfbb" stopOpacity="0" />
            <stop offset="50%" stopColor="#f4d49c" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#f5dfbb" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="capitalPlatform" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#726b68" />
            <stop offset="100%" stopColor="#e8e1d7" />
          </linearGradient>
          <filter id="capitalShadow" x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow dx="0" dy="14" stdDeviation="18" floodColor="#28185f" floodOpacity="0.1" />
          </filter>
          <radialGradient id="capitalGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff0c7" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#fff0c7" stopOpacity="0" />
          </radialGradient>
        </defs>
        <path d="M146 206 C244 206, 286 172, 360 172 S484 206, 610 206" stroke="url(#capitalBeam)" strokeWidth="8" fill="none" strokeLinecap="round">
          <animate attributeName="opacity" values="0.45;1;0.45" dur="4.6s" repeatCount="indefinite" />
        </path>
        <path d="M160 222 C252 222, 298 186, 364 186 S490 220, 620 220" stroke="url(#capitalBeam)" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.68">
          <animate attributeName="opacity" values="0.18;0.72;0.18" dur="5.4s" repeatCount="indefinite" />
        </path>

        <g transform="translate(34 138)" filter="url(#capitalShadow)">
          <animateTransform attributeName="transform" type="translate" values="34 138;34 132;34 138" dur="6.3s" repeatCount="indefinite" />
          <rect x="10" y="38" width="116" height="64" rx="6" fill="#e8e1d7" />
          <rect x="22" y="8" width="92" height="72" rx="6" fill="#ffffff" stroke="#e6d9dd" />
          <rect x="32" y="20" width="20" height="48" fill="#b7bcc5" />
          <rect x="58" y="26" width="18" height="42" fill="#d4d7de" />
          <rect x="82" y="18" width="22" height="50" fill="#c0c5ce" />
          <rect x="28" y="84" width="82" height="22" rx="11" fill="#fffdfa" stroke="#e6d9dd" />
          <text x="69" y="98" textAnchor="middle" fontSize="11" fill="#7a7779">Limited Access</text>
          <rect x="24" y="110" width="66" height="20" rx="10" fill="#fffdfa" stroke="#e6d9dd" />
          <text x="57" y="123" textAnchor="middle" fontSize="10" fill="#8f7f7f">No Rating</text>
        </g>

        <g transform="translate(226 108)" filter="url(#capitalShadow)">
          <ellipse cx="134" cy="116" rx="150" ry="40" fill="url(#capitalGlow)" />
          <ellipse cx="134" cy="112" rx="122" ry="34" fill="url(#capitalPlatform)" />
          <ellipse cx="134" cy="104" rx="90" ry="24" fill="#ffffff" stroke="#eadfce" />
          <rect x="84" y="90" width="100" height="34" rx="10" fill="#fffdfa" stroke="#e8dcca" />
          <text x="134" y="112" textAnchor="middle" fontSize="17" fontWeight="600" fill="#5b5661">TreGo Network</text>

          {[
            { x: 52, y: 28, value: "₹4.95 Cr" },
            { x: 134, y: 10, value: "Structuring" },
            { x: 214, y: 28, value: "₹5.10 Cr" },
            { x: 262, y: 52, value: "₹5.70 Cr" },
          ].map((chip) => (
            <g key={chip.value} transform={`translate(${chip.x} ${chip.y})`}>
              <animateTransform attributeName="transform" type="translate" values={`${chip.x} ${chip.y};${chip.x} ${chip.y - 5};${chip.x} ${chip.y}`} dur="5.2s" repeatCount="indefinite" />
              <rect width="82" height="28" rx="14" fill="#ffffff" stroke="#e6d9dd" />
              <text x="41" y="18" textAnchor="middle" fontSize="11" fill="#666b79">{chip.value}</text>
            </g>
          ))}
        </g>

        <g transform="translate(566 110)" filter="url(#capitalShadow)">
          <animateTransform attributeName="transform" type="translate" values="566 110;566 104;566 110" dur="6.1s" repeatCount="indefinite" />
          <rect x="18" y="24" width="28" height="94" rx="4" fill="#9499a4" />
          <rect x="44" y="12" width="42" height="106" rx="5" fill="#e3ddd6" />
          <rect x="82" y="2" width="54" height="116" rx="6" fill="#fffdfa" stroke="#e6d9dd" />
          <path d="M40 132 C72 118, 106 92, 142 46" fill="none" stroke="#d8a45f" strokeWidth="8" strokeLinecap="round" />
          <path d="M134 38 l18 8 -14 14" fill="none" stroke="#d8a45f" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
          <rect x="80" y="132" width="54" height="32" rx="7" fill="#353845" />
          <ellipse cx="62" cy="142" rx="12" ry="4.5" fill="#efcf98" />
          <ellipse cx="62" cy="149" rx="12" ry="4.5" fill="#d3a860" />
          <ellipse cx="92" cy="126" rx="12" ry="4.5" fill="#efcf98" />
          <ellipse cx="92" cy="133" rx="12" ry="4.5" fill="#d3a860" />
        </g>
      </svg>

      <div className="mt-4 grid gap-3 border-t border-[#e9dde2] pt-4 sm:grid-cols-3">
        {[
          ["01", "Advisory"],
          ["02", "Structuring"],
          ["03", "Capital Access"],
        ].map(([count, label]) => (
          <div key={label}>
            <div className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[#b86140]">{count}</div>
            <div className="mt-1 text-[0.9rem] font-semibold leading-6 text-[#2c204d]">{label}</div>
          </div>
        ))}
      </div>
    </PosterCanvas>
  );
}

function PosterCanvas({
  eyebrow,
  children,
  tone = "purple",
}: {
  eyebrow: string;
  children: ReactNode;
  tone?: "purple" | "blue" | "light" | "lightBlue";
}) {
  const background =
    tone === "blue"
      ? "bg-[linear-gradient(135deg,#18324f_0%,#2d587d_100%)]"
      : tone === "light"
        ? "bg-[linear-gradient(135deg,#fcfaf6_0%,#f4eef9_100%)]"
        : tone === "lightBlue"
          ? "bg-[linear-gradient(135deg,#f8fbff_0%,#eaf4fb_100%)]"
      : "bg-[linear-gradient(135deg,#171f49_0%,#31265e_100%)]";

  return (
    <div className={`relative h-full w-full overflow-hidden ${background}`}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.38),transparent_30%)]" />
      <div className="relative z-10 px-8 py-8 sm:px-10 sm:py-10">
        <div className="text-[0.76rem] font-semibold uppercase tracking-[0.28em] text-[#7b88a1]">{eyebrow}</div>
        <div className="mt-6">{children}</div>
      </div>
    </div>
  );
}
