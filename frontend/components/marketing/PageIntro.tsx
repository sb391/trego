export function PageIntro({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="mx-auto max-w-7xl px-4 pt-16 sm:px-8 sm:pt-22 lg:px-12 lg:pt-24">
      <div className="max-w-3xl">
        <p className="text-[0.64rem] font-semibold uppercase tracking-[0.24em] text-[#b45a3c] sm:text-[0.68rem] sm:tracking-[0.3em]">{eyebrow}</p>
        <h1 className="mt-3.5 max-w-[14ch] text-[1.48rem] font-extrabold leading-[1.06] tracking-[-0.05em] text-[#231f49] sm:mt-4 sm:max-w-[16ch] sm:text-[1.95rem] sm:leading-none lg:text-[2.2rem]">
          {title}
        </h1>
        <p className="mt-3.5 max-w-2xl text-[0.92rem] leading-7 text-[#69798b] sm:mt-5 sm:text-[0.95rem]">{description}</p>
      </div>
    </div>
  );
}
