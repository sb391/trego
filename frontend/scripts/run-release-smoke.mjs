import { spawn } from "node:child_process";

import { runSmokeTest } from "./smoke-critical-routes.mjs";

const BASE_URL = process.env.SMOKE_BASE_URL ?? "http://127.0.0.1:3100";
const HEALTH_URL = `${BASE_URL}/api/health`;

async function waitForHealth(timeoutMs = 60_000) {
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(HEALTH_URL, { cache: "no-store" });
      if (response.ok) {
        return;
      }
    } catch {}

    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  throw new Error(`Timed out waiting for health check at ${HEALTH_URL}`);
}

async function main() {
  const server = spawn("npx", ["next", "start", "-H", "127.0.0.1", "-p", "3100"], {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
  });

  try {
    await waitForHealth();
    await runSmokeTest(BASE_URL);
  } finally {
    server.kill("SIGTERM");
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
