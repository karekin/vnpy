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
const socialHotApiBase = (
  process.env.SOCIAL_HOT_INTERNAL_API_URL ||
  process.env.TENX_INTERNAL_API_URL ||
  process.env.TENX_DEERFLOW_API_URL ||
  process.env.NEXT_PUBLIC_SOCIAL_HOT_API_URL ||
  process.env.NEXT_PUBLIC_TENX_HUNTER_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  env.SOCIAL_HOT_INTERNAL_API_URL ||
  env.TENX_INTERNAL_API_URL ||
  env.TENX_DEERFLOW_API_URL ||
  env.NEXT_PUBLIC_SOCIAL_HOT_API_URL ||
  env.NEXT_PUBLIC_TENX_HUNTER_API_URL ||
  env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

export async function GET(req: Request) {
  const incomingUrl = new URL(req.url);
  const target = `${socialHotApiBase}/api/v1/social-hot-stocks${incomingUrl.search}`;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");

  const upstream = await fetch(target, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
