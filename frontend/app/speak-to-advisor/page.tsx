import { ResponsiveContactPanels } from "../../components/marketing/ContactPanels";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { PageIntro } from "../../components/marketing/PageIntro";
import { Reveal } from "../../components/marketing/Reveal";

export default function SpeakToAdvisorPage() {
  return (
    <MarketingShell>
      <section className="bg-[linear-gradient(180deg,#f8f4ee_0%,#fbf8f4_100%)] pb-20 sm:pb-24">
        <PageIntro
          eyebrow="Speak to Advisor"
          title="Talk through your next capital move with TreGo."
          description="This page is for businesses that want to discuss credit simulation, rating preparation, TReDS readiness, or broader capital positioning directly."
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
