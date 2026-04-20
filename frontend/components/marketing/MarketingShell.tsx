import type { ReactNode } from "react";

import { BackNav } from "./BackNav";
import { PrimaryNav } from "./PrimaryNav";
import { SiteFooter } from "./SiteFooter";

export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f8f4ee] text-[#121b30]">
      <PrimaryNav />
      <BackNav />
      <main>{children}</main>
      <SiteFooter />
    </div>
  );
}
