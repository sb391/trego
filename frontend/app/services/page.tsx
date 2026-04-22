import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PageIntro } from "../../components/marketing/PageIntro";
import { Reveal } from "../../components/marketing/Reveal";
import { ServiceOverviewCard } from "../../components/marketing/ServiceOverviewCard";
import { serviceCards } from "../../components/marketing/site-data";

export default function ServicesPage() {
  return (
    <MarketingShell>
      <section className="bg-[linear-gradient(180deg,#f8f4ee_0%,#fbf8f4_100%)] pb-20 sm:pb-24">
        <PageIntro
          eyebrow="Services"
          title="Four service lines built around credit, readiness, and capital movement."
          description="TreGo is designed to help businesses simulate position, improve readiness, unlock TReDS access, and prepare for larger institutional conversations."
        />

        <div className="mx-auto mt-10 max-w-7xl px-5 sm:mt-14 sm:px-8 lg:px-12">
          <div className="grid auto-rows-fr grid-cols-2 gap-4 sm:gap-6 md:grid-cols-2 xl:grid-cols-4">
            {serviceCards.map((card, index) => (
              <Reveal key={card.slug} delay={index * 0.04}>
                <ServiceOverviewCard
                  title={card.title}
                  tag={card.tag}
                  summary={card.summary}
                  href={`/services/${card.slug}`}
                  tone={index % 2 === 0 ? "light" : "dark"}
                />
              </Reveal>
            ))}
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
