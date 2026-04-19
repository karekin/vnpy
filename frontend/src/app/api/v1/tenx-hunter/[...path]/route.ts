import { readFileSync } from "fs";
import { resolve } from "path";

function loadLocalEnv() {
  const result: Record<string, string> = {};
  const candidates = [
    resolve(process.cwd(), "../.env.tushare.local"),
    resolve(process.cwd(), ".env.local"),
  ];

  for (const path of candidates) {
    try {
      const content = readFileSync(path, "utf-8");
      for (const raw of content.split("\n")) {
        const line = raw.trim();
        if (!line || line.startsWith("#") || !line.includes("=")) {
          continue;
        }

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
const tenxApiBase = (
  process.env.TENX_DEERFLOW_API_URL ||
  process.env.NEXT_PUBLIC_TENX_HUNTER_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  env.TENX_DEERFLOW_API_URL ||
  env.NEXT_PUBLIC_TENX_HUNTER_API_URL ||
  env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8002"
).replace(/\/$/, "");

async function proxyTenxRequest(
  req: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const incomingUrl = new URL(req.url);
  const target = `${tenxApiBase}/api/v1/tenx-hunter/${path.join("/")}${incomingUrl.search}`;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");

  const contentType = req.headers.get("content-type") ?? "";
  let body: BodyInit | undefined;

  if (req.method !== "GET" && req.method !== "HEAD") {
    if (contentType.includes("multipart/form-data")) {
      headers.delete("content-type");
      body = await req.formData();
    } else {
      body = await req.text();
    }
  }

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body,
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

export async function GET(
  req: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyTenxRequest(req, context);
}

export async function POST(
  req: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyTenxRequest(req, context);
}

export async function PATCH(
  req: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyTenxRequest(req, context);
}

export async function PUT(
  req: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyTenxRequest(req, context);
}

export async function DELETE(
  req: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyTenxRequest(req, context);
}
