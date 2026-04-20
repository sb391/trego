import { ReactNode } from "react";

type SectionHeadingProps = {
  eyebrow: string;
  title: string;
  description: ReactNode;
  centered?: boolean;
  invert?: boolean;
};

export function SectionHeading({
  eyebrow,
  title,
  description,
  centered = false,
  invert = false,
}: SectionHeadingProps) {
  return (
    <div className={centered ? "mx-auto max-w-3xl text-center" : "max-w-3xl"}>
      <span
        className={[
          "inline-flex items-center rounded-full border px-3 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.28em]",
          invert
            ? "border-white/15 bg-white/5 text-goldSoft"
            : "border-gold/20 bg-gold/10 text-navy",
        ].join(" ")}
      >
        {eyebrow}
      </span>
      <h2
        className={[
          "mt-6 font-display text-4xl leading-none tracking-[-0.03em] sm:text-5xl",
          invert ? "text-cloud" : "text-ink",
        ].join(" ")}
      >
        {title}
      </h2>
      <div className={["mt-5 text-base leading-7 sm:text-lg", invert ? "text-cloud/76" : "text-steel"].join(" ")}>
        {description}
      </div>
    </div>
  );
}
