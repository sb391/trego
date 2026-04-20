"use client";

import { useRouter, usePathname } from "next/navigation";

export function BackNav() {
  const router = useRouter();
  const pathname = usePathname();

  if (pathname === "/") {
    return null;
  }

  return (
    <div className="border-b border-[#efe3df] bg-white/82 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 py-2.5 sm:px-8 sm:py-3 lg:px-12">
        <button
          type="button"
          onClick={() => {
            if (window.history.length > 1) {
              router.back();
              return;
            }
            router.push("/");
          }}
          className="interactive-press inline-flex items-center gap-2 rounded-full border border-[#ead8d1] bg-white px-3.5 py-2 text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-[#7f4e40] shadow-[0_8px_18px_rgba(10,37,64,0.03)] transition hover:border-[#d8c3ba] hover:bg-[#fffaf8] sm:px-4 sm:text-[0.78rem] sm:tracking-[0.16em]"
        >
          <span aria-hidden="true">←</span>
          <span>Back</span>
        </button>
      </div>
    </div>
  );
}
