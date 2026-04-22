import { ResponsiveContactPanels } from "../../components/marketing/ContactPanels";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PageIntro } from "../../components/marketing/PageIntro";
import { Reveal } from "../../components/marketing/Reveal";

export default function ContactPage() {
  return (
    <MarketingShell>
      <section className="bg-[linear-gradient(180deg,#f8f4ee_0%,#fbf8f4_100%)] pb-20 sm:pb-24">
        <PageIntro
          eyebrow="Contact"
          title="Start the conversation with more clarity."
          description="Whether you are preparing for rating, lenders, or TReDS, the next capital conversation should begin from a stronger place."
        />

        <div className="mx-auto mt-14 max-w-7xl px-5 sm:px-8 lg:px-12">
          <Reveal>
            <ResponsiveContactPanels />
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
