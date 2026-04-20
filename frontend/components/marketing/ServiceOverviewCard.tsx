import Link from "next/link";

export function ServiceOverviewCard({
  title,
  tag,
  summary,
  href,
  tone = "light",
}: {
  title: string;
  tag: string;
  summary: string;
  href: string;
  tone?: "light" | "dark";
}) {
  const isDark = tone === "dark";

  return (
    <Link
      href={href}
      className={[
        "flex h-full min-h-[12rem] flex-col rounded-[1.4rem] border px-4.5 py-4.5 shadow-[0_16px_34px_rgba(10,37,64,0.04)] transition hover:-translate-y-1 sm:min-h-[13rem] sm:rounded-[1.55rem] sm:px-6 sm:py-6",
        isDark
          ? "border-[#1b2048] bg-[linear-gradient(135deg,#12193b_0%,#24184d_100%)] text-white"
          : "border-[#ece2e6] bg-[linear-gradient(180deg,#ffffff_0%,#fbf8f4_100%)] text-[#171f37]",
      ].join(" ")}
    >
      <div
        className={[
          "inline-flex w-fit rounded-full px-3.5 py-1.5 text-[0.62rem] font-semibold uppercase tracking-[0.18em] sm:px-4 sm:py-2 sm:text-[0.68rem] sm:tracking-[0.22em]",
          isDark ? "border border-white/12 bg-white/8 text-[#f0dfcb]" : "border border-[#eadde1] bg-white text-[#b45a3c]",
        ].join(" ")}
      >
        {tag}
      </div>

      <h3 className="mt-3.5 max-w-[13ch] text-[1.04rem] font-bold leading-[1.16] tracking-[-0.04em] sm:mt-4 sm:text-[1.24rem]">
        {title}
      </h3>
      <p className={["mt-2.5 max-w-[24ch] text-[0.84rem] leading-6 sm:mt-3 sm:max-w-[22ch] sm:text-[0.88rem]", isDark ? "text-white/74" : "text-[#67788b]"].join(" ")}>
        {summary}
      </p>

      <div className={["mt-auto pt-4 text-[0.68rem] font-semibold uppercase tracking-[0.18em] sm:pt-5 sm:text-[0.72rem] sm:tracking-[0.22em]", isDark ? "text-[#f0dfcb]" : "text-[#b45a3c]"].join(" ")}>
        View service
      </div>
    </Link>
  );
}
