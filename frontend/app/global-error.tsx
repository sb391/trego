"use client";

import { useEffect } from "react";

import * as Sentry from "@sentry/nextjs";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body className="bg-[#F8F6F2] text-[#0B1F3B]">
        <main className="flex min-h-screen items-center justify-center px-6 py-20">
          <div className="w-full max-w-xl rounded-[32px] border border-[#E8DDD2] bg-white px-8 py-12 shadow-[0_18px_60px_rgba(11,31,59,0.08)]">
            <p className="mb-4 text-sm uppercase tracking-[0.3em] text-[#9A5A36]">
              Runtime interruption
            </p>
            <h1 className="font-serif text-4xl leading-tight text-[#0B1F3B]">
              We hit an unexpected issue.
            </h1>
            <p className="mt-4 text-base leading-8 text-[#5F7086]">
              The incident has been captured for review. Please try the page again, and if the
              issue continues we can investigate it with the request trace.
            </p>
            <button
              className="mt-8 inline-flex items-center justify-center rounded-full bg-[#9A4C28] px-7 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-white transition hover:bg-[#833f20]"
              onClick={reset}
              type="button"
            >
              Try again
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
