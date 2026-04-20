"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

type PreviewPage = {
  label: string;
  path: string;
  description: string;
};

type PreviewDevice = {
  label: string;
  width: number;
  height: number;
  frameWidth: number;
};

const previewPages: PreviewPage[] = [
  {
    label: "Home",
    path: "/",
    description: "Homepage hero, mobile spacing, CTA sizing, and section rhythm.",
  },
  {
    label: "About",
    path: "/about",
    description: "Leadership, cards, and long-form content balance on mobile.",
  },
  {
    label: "Services",
    path: "/services",
    description: "Service list density, card stacking, and section pacing.",
  },
  {
    label: "Credit Simulation",
    path: "/services/credit-simulation",
    description: "Service-detail page layout, copy balance, and hero composition.",
  },
  {
    label: "Contact",
    path: "/contact",
    description: "Lead form usability, office cards, and CTA touch targets.",
  },
];

const previewDevices: PreviewDevice[] = [
  { label: "375px", width: 375, height: 812, frameWidth: 286 },
  { label: "390px", width: 390, height: 844, frameWidth: 296 },
  { label: "430px", width: 430, height: 932, frameWidth: 322 },
];

export function MobilePreviewStudio() {
  const [selectedPath, setSelectedPath] = useState(previewPages[0]?.path ?? "/");

  const selectedPage = useMemo(
    () => previewPages.find((page) => page.path === selectedPath) ?? previewPages[0],
    [selectedPath],
  );

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#f6f2ea_0%,#fbf8f3_100%)] text-[#0b1f3b]">
      <section className="border-b border-[#eadfe0] bg-[radial-gradient(circle_at_top_left,rgba(207,167,110,0.14),transparent_18%),linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,255,255,0.82))]">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.34em] text-[#b45a3c]">
                Mobile Validation Studio
              </p>
              <h1 className="mt-3 font-display text-[2rem] font-semibold leading-[1.02] tracking-[-0.04em] text-[#2f255f] sm:text-[2.6rem]">
                TreGo mobile preview, without touching desktop.
              </h1>
              <p className="mt-4 max-w-[48rem] text-[0.98rem] leading-7 text-[#617184] sm:text-[1.04rem]">
                Use this screen to review the live website inside exact mobile-width frames. The production desktop
                layout stays untouched; this is only a local validation layer for `375`, `390`, and `430`.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Link
                href={selectedPage.path}
                className="interactive-press inline-flex items-center justify-center rounded-full bg-[#b45a3c] px-5 py-3 text-[0.8rem] font-semibold uppercase tracking-[0.16em] text-white shadow-[0_12px_24px_rgba(180,90,60,0.2)] transition hover:bg-[#a24e34]"
              >
                Open selected page
              </Link>
              <Link
                href="/"
                className="interactive-press inline-flex items-center justify-center rounded-full border border-[#d9cdd2] bg-white px-5 py-3 text-[0.8rem] font-semibold uppercase tracking-[0.16em] text-[#2f255f] transition hover:border-[#cdbfc6]"
              >
                Back to website
              </Link>
            </div>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-[1.8rem] border border-[#eadfe0] bg-white/92 p-4 shadow-[0_18px_40px_rgba(10,37,64,0.05)] sm:p-5">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#8b9ab0]">Preview page</p>
              <div className="mt-3 flex flex-wrap gap-2.5">
                {previewPages.map((page) => {
                  const isActive = page.path === selectedPath;
                  return (
                    <button
                      key={page.path}
                      type="button"
                      onClick={() => setSelectedPath(page.path)}
                      className={`interactive-press rounded-full px-4 py-2.5 text-[0.78rem] font-semibold uppercase tracking-[0.14em] transition ${
                        isActive
                          ? "border border-[#b45a3c] bg-[#b45a3c] text-white shadow-[0_12px_24px_rgba(180,90,60,0.18)]"
                          : "border border-[#e6dadd] bg-[#fcf9f6] text-[#5f6d80] hover:border-[#d6c8cc] hover:text-[#2f255f]"
                      }`}
                    >
                      {page.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-[1.8rem] border border-[#eadfe0] bg-[linear-gradient(180deg,#fffdfa_0%,#faf6f2_100%)] p-4 shadow-[0_18px_40px_rgba(10,37,64,0.04)] sm:p-5">
              <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#8b9ab0]">What to validate</p>
              <h2 className="mt-3 text-[1.1rem] font-semibold leading-6 text-[#2f255f]">{selectedPage.label}</h2>
              <p className="mt-2 text-[0.93rem] leading-7 text-[#617184]">{selectedPage.description}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
        <div className="grid gap-6 xl:grid-cols-3">
          {previewDevices.map((device) => (
            <MobileDeviceFrame key={`${selectedPath}-${device.width}`} device={device} path={selectedPath} />
          ))}
        </div>
      </section>
    </main>
  );
}

function MobileDeviceFrame({ device, path }: { device: PreviewDevice; path: string }) {
  const scale = device.frameWidth / device.width;
  const frameHeight = Math.round(device.height * scale);

  return (
    <section className="rounded-[2rem] border border-[#e7dadd] bg-[linear-gradient(180deg,#fffdfb_0%,#faf6f2_100%)] p-4 shadow-[0_22px_48px_rgba(10,37,64,0.08)]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-[#b45a3c]">{device.label}</p>
          <p className="mt-1 text-[0.88rem] text-[#6a7a8c]">
            {device.width} x {device.height}
          </p>
        </div>
        <div className="rounded-full border border-[#e7dadd] bg-white px-3 py-1.5 text-[0.72rem] font-semibold uppercase tracking-[0.2em] text-[#8b9ab0]">
          Live
        </div>
      </div>

      <div className="mt-4 flex justify-center">
        <div
          className="relative overflow-hidden rounded-[2.2rem] border-[8px] border-[#17182b] bg-[#17182b] shadow-[0_24px_56px_rgba(10,37,64,0.18)]"
          style={{ width: device.frameWidth + 16, height: frameHeight + 28 }}
        >
          <div className="absolute left-1/2 top-2 z-10 h-5 w-28 -translate-x-1/2 rounded-full bg-[#0b0c19]" />
          <div className="absolute inset-x-0 bottom-0 h-6 bg-[#17182b]" />
          <div
            className="absolute left-0 top-0 origin-top-left overflow-hidden bg-white"
            style={{ width: device.width, height: device.height, transform: `scale(${scale})` }}
          >
            <iframe
              key={`${path}-${device.width}`}
              src={path}
              title={`${path} preview at ${device.width}px`}
              className="h-full w-full border-0 bg-white"
              width={device.width}
              height={device.height}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
