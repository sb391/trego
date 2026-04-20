"use client";

import Image from "next/image";

export function HeroValueIllustration() {
  return (
    <div className="relative mx-auto mt-3 w-full max-w-[34rem] px-1 sm:mt-0 sm:max-w-[44rem] sm:px-0 lg:max-w-[49rem]">
      <div className="pointer-events-none absolute inset-x-[6%] top-[6%] h-[78%] rounded-[3rem] bg-[radial-gradient(circle_at_center,rgba(255,228,193,0.42),transparent_68%)] blur-3xl" />
      <div className="pointer-events-none absolute -left-[6%] top-[10%] h-36 w-36 rounded-full bg-[radial-gradient(circle,rgba(230,203,255,0.34),transparent_70%)] blur-2xl" />
      <div className="pointer-events-none absolute -right-[2%] bottom-[8%] h-44 w-44 rounded-full bg-[radial-gradient(circle,rgba(255,211,164,0.32),transparent_70%)] blur-2xl" />

      <div className="relative">
        <div className="pointer-events-none absolute inset-0 z-10 bg-[radial-gradient(circle_at_24%_18%,rgba(255,255,255,0.44),transparent_24%)]" />
        <div className="pointer-events-none absolute inset-0 z-10 bg-[radial-gradient(circle_at_78%_28%,rgba(255,219,170,0.24),transparent_22%)]" />
        <Image
          src="/assets/hero.avif"
          alt="TreGo Capital hero illustration"
          width={1536}
          height={1024}
          priority
          sizes="(min-width: 1280px) 54vw, (min-width: 1024px) 52vw, 92vw"
          className="relative z-0 h-auto w-full object-contain"
          style={{
            filter: "drop-shadow(0 24px 32px rgba(31, 24, 61, 0.09))",
            WebkitMaskImage:
              "radial-gradient(circle at center, rgba(0,0,0,1) 56%, rgba(0,0,0,0.94) 72%, rgba(0,0,0,0.52) 86%, rgba(0,0,0,0) 100%)",
            maskImage:
              "radial-gradient(circle at center, rgba(0,0,0,1) 56%, rgba(0,0,0,0.94) 72%, rgba(0,0,0,0.52) 86%, rgba(0,0,0,0) 100%)",
          }}
        />
      </div>
    </div>
  );
}
