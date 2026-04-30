import { readFileSync } from "fs";
import { resolve } from "path";

function loadLocalEnv() {
  const result: Record<string, string> = {};
  const candidates = [resolve(process.cwd(), "../.env.tushare.local"), resolve(process.cwd(), ".env.local")];

  for (const path of candidates) {
    try {
      const content = readFileSync(path, "utf-8");
      for (const raw of content.split("\n")) {
        const line = raw.trim();
        if (!line || line.startsWith("#") || !line.includes("=")) continue;
        const cleaned = line.startsWith("export ") ? line.slice(7) : line;
        const [key, ...rest] = cleaned.split("=");
        result[key.trim()] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
      }
    } catch {
      continue;
    }
  }

  return result;
}

const env = loadLocalEnv();
const smartAllocationApiBases = Array.from(
  new Set(
    [
      process.env.NEXT_PUBLIC_SMART_ALLOCATION_API_URL,
      process.env.NEXT_PUBLIC_API_URL,
      env.NEXT_PUBLIC_SMART_ALLOCATION_API_URL,
      env.NEXT_PUBLIC_API_URL,
      "http://127.0.0.1:8003",
      "http://127.0.0.1:8000",
    ]
      .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      .map((item) => item.replace(/\/$/, "")),
  ),
);

function shouldTryNextBackend(status: number) {
  return [404, 500, 502, 503, 504].includes(status);
}

async function proxySmartAllocationRequest(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const incomingUrl = new URL(req.url);

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");

  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();
  let lastResponse: Response | null = null;
  let lastError: unknown = null;

  for (const apiBase of smartAllocationApiBases) {
    const target = `${apiBase}/api/v1/smart-allocation/${path.join("/")}${incomingUrl.search}`;
    try {
      const upstream = await fetch(target, {
        method: req.method,
        headers,
        body,
        cache: "no-store",
      });
      if (upstream.ok || !shouldTryNextBackend(upstream.status)) {
        lastResponse = upstream;
        break;
      }
      lastResponse = upstream;
    } catch (error) {
      lastError = error;
    }
  }

  if (!lastResponse) {
    return Response.json(
      { detail: lastError instanceof Error ? lastError.message : "smart allocation backend unavailable" },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers(lastResponse.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new Response(lastResponse.body, {
    status: lastResponse.status,
    statusText: lastResponse.statusText,
    headers: responseHeaders,
  });
}

export async function GET(req: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxySmartAllocationRequest(req, context);
}

export async function POST(req: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxySmartAllocationRequest(req, context);
}

export async function PUT(req: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxySmartAllocationRequest(req, context);
}
