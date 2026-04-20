import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PageIntro } from "../../components/marketing/PageIntro";
import { Reveal } from "../../components/marketing/Reveal";

const steps = [
  {
    step: "01",
    title: "Read the current position",
    text: "We start with financials, credit posture, and working-capital signals before the market forms its own first impression.",
  },
  {
    step: "02",
    title: "Identify what matters most",
    text: "The process stays focused on the few changes most likely to affect agency, lender, or platform confidence.",
  },
  {
    step: "03",
    title: "Prepare the business better",
    text: "We shape management preparation, documentation quality, and capital positioning before formal conversations begin.",
  },
  {
    step: "04",
    title: "Enter with more control",
    text: "The result is a cleaner capital story, clearer readiness, and fewer surprises in live discussions.",
  },
];

export default function ApproachPage() {
  return (
    <MarketingShell>
      <section className="bg-[linear-gradient(180deg,#f8f4ee_0%,#fbf8f4_100%)] pb-20 sm:pb-24">
        <PageIntro
          eyebrow="Approach"
          title="A cleaner process from raw financials to live capital conversations."
          description="TreGo keeps the advisory process structured and usable, so preparation improves before the outside market begins interpreting the business."
        />

        <div className="mx-auto mt-14 max-w-7xl px-5 sm:px-8 lg:px-12">
          <div className="grid gap-5 md:grid-cols-2">
            {steps.map((step, index) => (
              <Reveal key={step.step} delay={index * 0.04}>
                <div className="rounded-[1.7rem] border border-[#ece2e6] bg-white px-6 py-7 shadow-[0_16px_34px_rgba(10,37,64,0.04)]">
                  <div className="text-[2rem] font-bold tracking-[-0.05em] text-[#d2c0bf]">{step.step}</div>
                  <h3 className="mt-4 text-[1.2rem] font-semibold text-[#241d39]">{step.title}</h3>
                  <p className="mt-3 text-[0.96rem] leading-8 text-[#69798b]">{step.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
