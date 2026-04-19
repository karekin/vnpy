import type { UIMessage } from "ai";

export type NormalizedChatPart =
  | {
      type: "text";
      text: string;
    }
  | {
      type: "file";
      filename?: string;
      mediaType?: string;
    };

type LooseUIMessage = UIMessage & {
  content?: unknown;
  experimental_attachments?: Array<Record<string, unknown>>;
};

function pickString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return undefined;
}

function normalizeFilePart(candidate: Record<string, unknown>): NormalizedChatPart | null {
  const filename = pickString(
    candidate.filename,
    candidate.name,
    candidate.path,
    candidate.virtual_path,
    candidate.url,
  );
  const mediaType = pickString(
    candidate.mediaType,
    candidate.mimeType,
    candidate.contentType,
    candidate.mime_type,
  );

  if (!filename && !mediaType) {
    return null;
  }

  return {
    type: "file",
    filename,
    mediaType,
  };
}

export function extractNormalizedMessageParts(message?: LooseUIMessage | null): NormalizedChatPart[] {
  if (!message || typeof message !== "object") {
    return [];
  }

  const parts: NormalizedChatPart[] = [];

  const pushText = (value: unknown) => {
    if (typeof value !== "string") {
      return;
    }

    const text = value.trim();
    if (!text) {
      return;
    }

    parts.push({
      type: "text",
      text,
    });
  };

  const pushFile = (value: unknown) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return;
    }

    const normalized = normalizeFilePart(value as Record<string, unknown>);
    if (normalized) {
      parts.push(normalized);
    }
  };

  if (Array.isArray(message.parts)) {
    for (const part of message.parts) {
      if (!part || typeof part !== "object") {
        continue;
      }

      const type = String((part as { type?: unknown }).type ?? "");
      if (type === "text") {
        pushText((part as { text?: unknown }).text);
        continue;
      }

      if (type === "file" || type === "image") {
        pushFile(part);
      }
    }
  }

  if (typeof message.content === "string") {
    pushText(message.content);
  } else if (Array.isArray(message.content)) {
    for (const item of message.content) {
      if (typeof item === "string") {
        pushText(item);
        continue;
      }

      if (!item || typeof item !== "object") {
        continue;
      }

      const part = item as Record<string, unknown>;
      const type = typeof part.type === "string" ? part.type : "";

      if (type === "text") {
        pushText(part.text);
        continue;
      }

      if (
        type === "file" ||
        type === "image" ||
        type === "input_file" ||
        type === "input_image"
      ) {
        pushFile(part);
      }
    }
  }

  if (Array.isArray(message.experimental_attachments)) {
    for (const attachment of message.experimental_attachments) {
      pushFile(attachment);
    }
  }

  return parts;
}
