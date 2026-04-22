const DEFAULT_BASE_URL = process.env.SMOKE_BASE_URL ?? "http://127.0.0.1:3100";

const routes = [
  { method: "GET", path: "/", expectedStatus: 200 },
  { method: "GET", path: "/about", expectedStatus: 200 },
  { method: "GET", path: "/capabilities", expectedStatus: 200 },
  { method: "GET", path: "/approach", expectedStatus: 200 },
  { method: "GET", path: "/contact", expectedStatus: 200 },
  { method: "GET", path: "/services", expectedStatus: 200 },
  { method: "GET", path: "/services/credit-simulation", expectedStatus: 200 },
  { method: "GET", path: "/services/rating-advisory", expectedStatus: 200 },
  { method: "GET", path: "/services/treds-enablement", expectedStatus: 200 },
  { method: "GET", path: "/services/capital-strategy", expectedStatus: 200 },
  { method: "GET", path: "/speak-to-advisor", expectedStatus: 200 },
  { method: "GET", path: "/admin/login", expectedStatus: 200, acceptedStatuses: [200, 307] },
  { method: "GET", path: "/api/health", expectedStatus: 200, expectHealth: true },
  {
    method: "POST",
    path: "/api/inquiries",
    expectedStatus: 200,
    expectInquiryMode: "smoke",
    body: {
      fullName: "Smoke Test User",
      email: "smoke@test.example",
      company: "TreGo Smoke Industries",
      inquiryType: "Credit Rating Simulation",
      message: "Smoke-test submission for release verification.",
      phone: "+91 9999999999",
      sourcePage: "/smoke",
    },
    headers: {
      "Content-Type": "application/json",
      "x-smoke-test": "1",
    },
  },
];

async function parseJsonSafe(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function runSmokeTest(baseUrl = DEFAULT_BASE_URL) {
  const failures = [];

  for (const route of routes) {
    const url = `${baseUrl}${route.path}`;
    let response;

    try {
      response = await fetch(url, {
        method: route.method,
        headers: route.headers,
        body: route.body ? JSON.stringify(route.body) : undefined,
      });
    } catch (error) {
      failures.push(
        `${route.method} ${route.path} failed to fetch: ${error instanceof Error ? error.message : String(error)}`,
      );
      continue;
    }

    const payload = await parseJsonSafe(response);

    const acceptedStatuses = route.acceptedStatuses ?? [route.expectedStatus];

    if (!acceptedStatuses.includes(response.status)) {
      failures.push(
        `${route.method} ${route.path} returned ${response.status} (expected one of ${acceptedStatuses.join(", ")}).`,
      );
      continue;
    }

    if (route.expectHealth && (!payload || payload.ok !== true)) {
      failures.push(`${route.method} ${route.path} reported unhealthy payload: ${JSON.stringify(payload)}`);
    }

    if (route.expectInquiryMode && (!payload || payload.mode !== route.expectInquiryMode)) {
      failures.push(
        `${route.method} ${route.path} returned unexpected inquiry mode: ${JSON.stringify(payload)}`,
      );
    }
  }

  if (failures.length > 0) {
    throw new Error(`Smoke test failures:\n- ${failures.join("\n- ")}`);
  }

  console.log(`Smoke tests passed for ${baseUrl}`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSmokeTest(process.argv[2]).catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
