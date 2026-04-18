import Anthropic from "@anthropic-ai/sdk";
import {
  AnthropicAdapter,
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
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
const apiKey = process.env.MINIMAX_API_KEY || env.MINIMAX_API_KEY || "";
const baseURL = (
  process.env.MINIMAX_BASE_URL ||
  env.MINIMAX_BASE_URL ||
  "https://api.minimaxi.com/anthropic/v1"
).replace(/\/$/, "");
const model = process.env.MINIMAX_MODEL || env.MINIMAX_MODEL || "MiniMax-M2.7";

const anthropic = new Anthropic({
  apiKey,
  baseURL,
  defaultHeaders: {
    "anthropic-version": "2023-06-01",
  },
});

const runtime = new CopilotRuntime();
const serviceAdapter = new AnthropicAdapter({
  anthropic,
  model,
});

const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
  runtime,
  serviceAdapter,
  endpoint: "/api/copilotkit",
});

export const GET = handleRequest;
export const POST = handleRequest;
export const OPTIONS = handleRequest;
