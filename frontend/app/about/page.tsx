import Link from "next/link";
import Image from "next/image";

import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PageIntro } from "../../components/marketing/PageIntro";
import { Reveal } from "../../components/marketing/Reveal";

type FounderProfile = {
  name: string;
  role: string;
  initials: string;
  image?: string;
  imageClassName?: string;
  summary: string;
  bio: string[];
};

const founders: FounderProfile[] = [
  {
    name: "Saurabh Baggaru",
    role: "Co-Founder",
    initials: "SB",
    image: "/assets/saurabh-baggaru.avif",
    imageClassName: "object-cover object-top",
    summary: "IIT alumnus, operator, and fintech builder with 12+ years across digital credit growth, product, and scale.",
    bio: [
      "An IIT alumnus and fintech leader with 12+ years in scaling digital credit businesses.",
      "Ex-COO of India's second-largest credit marketplace and early member at PaySense ($185M PayU acquisition), with strengths across growth, acquisition, and product.",
    ],
  },
  {
    name: "Ashish Sharma",
    role: "Co-Founder",
    initials: "AS",
    image: "/assets/ashish-sharma.avif",
    imageClassName: "object-cover object-top",
    summary: "Credit and capital-access leader with operating depth across PaySense, PayU Finance, ICICI Bank, and PayPal.",
    bio: [
      "Operates at the intersection of credit, capital access, and financial technology. As a founding member of PaySense, he helped build a category-defining platform acquired by PayU for $185M.",
    ],
  },
];

export default function AboutPage() {
  return (
    <MarketingShell>
      <section className="bg-[linear-gradient(180deg,#f8f4ee_0%,#fbf8f4_100%)] pb-20 sm:pb-24">
        <PageIntro
          eyebrow="About"
          title="TreGo Capital is built to make capital conversations sharper."
          description="We help corporates approach rating agencies, lenders, and working-capital platforms with more preparation, more structure, and fewer surprises."
        />

        <div className="mx-auto mt-12 max-w-7xl px-4 sm:mt-14 sm:px-8 lg:px-12">
          <Reveal>
            <div className="grid gap-4 md:grid-cols-3 sm:gap-6">
              {[
                {
                  title: "Credit intelligence first",
                  text: "We begin with position, signal, and likely interpretation before the market defines them for you.",
                },
                {
                  title: "Advisory that stays usable",
                  text: "The work is designed to help real capital decisions move better, not to create reporting noise.",
                },
                {
                  title: "India-focused execution",
                  text: "TreGo is built for domestic credit, TReDS, lender, and institutional capital conversations in India.",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="rounded-[1.4rem] border border-[#ece2e6] bg-white px-5 py-6 shadow-[0_16px_34px_rgba(10,37,64,0.04)] sm:rounded-[1.6rem] sm:px-6 sm:py-7"
                >
                  <h3 className="text-[1.06rem] font-semibold text-[#241d39] sm:text-[1.2rem]">{item.title}</h3>
                  <p className="mt-3 text-[0.9rem] leading-7 text-[#69798b] sm:text-[0.96rem] sm:leading-8">{item.text}</p>
                </div>
              ))}
            </div>
          </Reveal>

          <Reveal>
            <div className="mt-8 rounded-[1.6rem] border border-[#ece2e6] bg-white px-5 py-6 shadow-[0_18px_42px_rgba(10,37,64,0.04)] sm:mt-10 sm:rounded-[2rem] sm:px-10 sm:py-8">
              <div className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
                <div>
                  <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b45a3c]">How we think</p>
                  <h2 className="mt-4 max-w-[15ch] text-[1.62rem] font-extrabold leading-[1.06] tracking-[-0.05em] text-[#2f255f] sm:text-[2.45rem]">
                    Capital readiness should be understood before it is tested.
                  </h2>
                </div>
                <div className="space-y-4 text-[0.92rem] leading-7 text-[#69798b] sm:text-[0.98rem] sm:leading-8">
                  <p>
                    That means reading the current position clearly, identifying what should improve first, and then
                    shaping the business for external conversations.
                  </p>
                  <p>
                    TreGo sits in that gap between raw financials and live capital response, helping businesses prepare
                    before the pressure becomes real.
                  </p>
                </div>
              </div>
            </div>
          </Reveal>

          <Reveal>
            <div className="mt-10 rounded-[1.75rem] border border-[#ece2e6] bg-white px-5 py-6 shadow-[0_18px_42px_rgba(10,37,64,0.04)] sm:mt-12 sm:rounded-[2.1rem] sm:px-8 sm:py-9 lg:px-9">
              <div className="mx-auto max-w-3xl text-center">
                <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b45a3c]">
                  Founding Partners
                </p>
                <h2 className="mt-4 text-[1.68rem] font-extrabold leading-[1.06] tracking-[-0.05em] text-[#2f255f] sm:text-[2.55rem]">
                  Meet the <span className="font-medium italic text-[#a54b32]">Founders</span>
                </h2>
                <p className="mt-4 text-[0.92rem] leading-7 text-[#6b7b8d] sm:text-[0.96rem]">
                  The leadership behind TreGo&apos;s credit intelligence, capital access, and execution discipline.
                </p>
              </div>

              <div className="mt-8 grid gap-5 lg:grid-cols-2">
                {founders.map((founder) => (
                  <article
                    key={founder.name}
                    className="overflow-hidden rounded-[1.75rem] border border-[#ece2e6] bg-[linear-gradient(180deg,#ffffff_0%,#fbf8f4_100%)] shadow-[0_16px_36px_rgba(10,37,64,0.04)]"
                  >
                    <div className="grid gap-0 lg:grid-cols-[0.76fr_1.24fr]">
                      <div className="relative min-h-[13.5rem] overflow-hidden border-b border-[#efe5e8] bg-[radial-gradient(circle_at_top_left,rgba(180,90,60,0.14),transparent_48%),linear-gradient(135deg,#f9f4ef_0%,#f1edf8_55%,#f8f5f2_100%)] sm:min-h-[15.5rem] lg:min-h-full lg:border-b-0 lg:border-r">
                        {founder.image ? (
                          <Image
                            src={founder.image}
                            alt={founder.name}
                            fill
                            sizes="(min-width: 1280px) 18vw, (min-width: 1024px) 24vw, 92vw"
                            className={founder.imageClassName}
                            priority={founder.name === "Saurabh Baggaru"}
                          />
                        ) : (
                          <>
                            <div className="absolute right-0 top-0 h-28 w-28 rounded-full bg-[radial-gradient(circle,rgba(180,90,60,0.12),transparent_70%)]" />
                            <div className="absolute bottom-0 left-0 h-24 w-24 rounded-full bg-[radial-gradient(circle,rgba(47,37,95,0.1),transparent_70%)]" />
                            <div className="absolute inset-x-0 top-0 h-24 bg-[linear-gradient(180deg,rgba(255,255,255,0.56),transparent)]" />
                            <div className="relative flex h-full min-h-[15.5rem] items-center justify-center px-8 py-8">
                              <div className="flex h-24 w-24 items-center justify-center rounded-[1.7rem] border border-white/70 bg-white/92 text-[2rem] font-bold tracking-[-0.05em] text-[#2f255f] shadow-[0_14px_30px_rgba(10,37,64,0.08)] backdrop-blur">
                                {founder.initials}
                              </div>
                            </div>
                          </>
                        )}
                        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-[linear-gradient(180deg,rgba(255,255,255,0)_0%,rgba(255,255,255,0.9)_100%)]" />
                      </div>

                      <div className="px-5 py-5 sm:px-7 sm:py-6">
                        <div className="inline-flex rounded-full border border-[#e5d5d9] bg-white px-3 py-1 text-[0.66rem] font-semibold uppercase tracking-[0.22em] text-[#a54b32]">
                          {founder.role}
                        </div>
                        <h3 className="mt-3.5 text-[1.32rem] font-bold leading-[1.05] tracking-[-0.045em] text-[#241d39] sm:text-[1.62rem]">
                          {founder.name}
                        </h3>
                        <p className="mt-2.5 text-[0.82rem] leading-6 text-[#69798b] sm:text-[0.84rem]">{founder.summary}</p>
                        <div className="mt-4 flex gap-3">
                          <div className="h-1.5 w-16 rounded-full bg-[#b45a3c]" />
                          <div className="h-1.5 w-9 rounded-full bg-[#ddd0d6]" />
                          <div className="h-1.5 w-6 rounded-full bg-[#ece3e6]" />
                        </div>
                        <div className="mt-4 space-y-2.5 text-[0.82rem] leading-6 text-[#69798b] sm:text-[0.85rem]">
                          {founder.bio.map((paragraph) => (
                            <p key={paragraph}>{paragraph}</p>
                          ))}
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </Reveal>

          <Reveal>
            <div className="mt-8 flex flex-col gap-3 sm:mt-10 sm:flex-row sm:gap-4">
              <Link
                href="/speak-to-advisor"
                className="interactive-press inline-flex items-center justify-center rounded-full bg-[#b45a3c] px-7 py-4 text-[0.92rem] font-semibold text-white shadow-[0_14px_28px_rgba(180,90,60,0.22)] transition hover:bg-[#a34c31] sm:px-8 sm:py-5 sm:text-sm"
              >
                Speak to Advisor
              </Link>
              <Link
                href="/services"
                className="interactive-press inline-flex items-center justify-center rounded-full border-2 border-[#d8cdd5] bg-white px-7 py-4 text-[0.92rem] font-semibold text-[#2f255f] transition hover:border-[#c9bec7] sm:px-8 sm:py-5 sm:text-sm"
              >
                Explore Services
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
