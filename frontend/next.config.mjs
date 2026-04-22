import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Keep dev output isolated from production builds so local refreshes
  // don't break when `next dev` and `next build` run close together.
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
};

export default withSentryConfig(nextConfig, {
  silent: true,
  disableLogger: true,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  sourcemaps: {
    disable: !process.env.SENTRY_AUTH_TOKEN,
  },
});
