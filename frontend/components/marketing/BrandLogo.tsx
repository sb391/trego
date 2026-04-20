import Link from "next/link";

export function BrandLogo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="group inline-flex items-center gap-2.5 sm:gap-3">
      <span className="inline-flex h-10 w-10 items-center justify-center rounded-[0.85rem] border border-[#e5d8e0] bg-white shadow-[0_10px_24px_rgba(10,37,64,0.04)] transition group-hover:border-[#d8c7d1] sm:h-11 sm:w-11 sm:rounded-[0.9rem]">
        <span className="relative block h-[1.1rem] w-[1.1rem] sm:h-5 sm:w-5">
          <span className="absolute bottom-0 left-0 h-2.5 w-1.5 rounded-sm bg-[#b45a3c]" />
          <span className="absolute bottom-0 left-2 h-4 w-1.5 rounded-sm bg-[#30146f]" />
          <span className="absolute bottom-0 left-4 h-5 w-1.5 rounded-sm bg-[#b45a3c]" />
        </span>
      </span>
      <div>
        <div className="font-sans text-[1.28rem] font-extrabold leading-none tracking-[-0.04em] text-[#30146f] sm:text-[1.7rem]">
          TreGo Capital
        </div>
        <div className="mt-0.5 text-[0.5rem] uppercase tracking-[0.26em] text-[#b45a3c] sm:mt-1 sm:text-[0.58rem] sm:tracking-[0.32em]">
          Credit Intelligence Advisory
        </div>
      </div>
    </Link>
  );
}
