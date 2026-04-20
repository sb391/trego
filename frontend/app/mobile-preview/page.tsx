import type { Metadata } from "next";

import { MobilePreviewStudio } from "../../components/marketing/MobilePreviewStudio";

export const metadata: Metadata = {
  title: "Mobile Preview | TreGo Capital",
  description: "Local mobile validation studio for TreGo Capital.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function MobilePreviewPage() {
  return <MobilePreviewStudio />;
}
