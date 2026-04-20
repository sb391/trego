import Link from "next/link";

import { BrandLogo } from "./BrandLogo";
import { OfficeAccordionList } from "./OfficeAccordion";
import { companyFooterLinks, serviceFooterLinks } from "./site-data";

export function SiteFooter() {
  return (
    <footer className="border-t border-[#ece2e6] bg-[#f4efe8]">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-8 sm:py-16 lg:grid-cols-[1fr_0.72fr_0.72fr_1.08fr] lg:gap-12 lg:px-12">
        <div className="max-w-md">
          <BrandLogo />
          <p className="mt-5 text-[0.95rem] leading-7 text-[#607182] sm:mt-6 sm:text-[1rem] sm:leading-8">
            Capital and credit advisory designed to help corporates prepare for rating, TReDS, lender, and larger
            funding conversations.
          </p>
        </div>

        <FooterList title="Company" items={companyFooterLinks} />
        <FooterList title="Services" items={serviceFooterLinks} />

        <div>
          <h3 className="text-[0.84rem] font-semibold uppercase tracking-[0.24em] text-[#2f255f]">Our offices</h3>
          <div className="mt-4 h-1 w-8 rounded-full bg-[#ddcad5]" />
          <div className="mt-6">
            <OfficeAccordionList variant="footer" />
          </div>
        </div>
      </div>

      <div className="border-t border-[#ece2e6]">
        <div className="mx-auto max-w-7xl px-4 py-6 text-[0.88rem] text-[#9aa8b6] sm:px-8 sm:text-[0.95rem] lg:px-12">
          © 2026 TreGo Capital. All rights reserved.
        </div>
      </div>
    </footer>
  );
}

function FooterList({
  title,
  items,
}: {
  title: string;
  items: ReadonlyArray<{ href: string; label: string }>;
}) {
  return (
    <div>
      <h3 className="text-[0.76rem] font-semibold uppercase tracking-[0.2em] text-[#2f255f] sm:text-[0.84rem] sm:tracking-[0.24em]">{title}</h3>
      <div className="mt-4 h-1 w-8 rounded-full bg-[#ddcad5]" />
      <ul className="mt-5 space-y-3.5 text-[0.98rem] text-[#607182] sm:mt-6 sm:space-y-4 sm:text-[1.05rem]">
        {items.map((item) => (
          <li key={item.href}>
            <Link href={item.href} className="transition hover:text-[#b45a3c]">
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
