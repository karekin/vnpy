import { extractNormalizedMessageParts } from "./message-parts";

describe("extractNormalizedMessageParts", () => {
  test("supports legacy string content without parts", () => {
    expect(
      extractNormalizedMessageParts({
        id: "msg-1",
        role: "user",
        content: "hello from legacy content",
      } as never),
    ).toEqual([
      {
        type: "text",
        text: "hello from legacy content",
      },
    ]);
  });

  test("keeps text and file parts from structured messages", () => {
    expect(
      extractNormalizedMessageParts({
        id: "msg-2",
        role: "user",
        parts: [
          { type: "text", text: "analyze this chart" },
          {
            type: "file",
            filename: "chart.png",
            mediaType: "image/png",
          },
        ],
      } as never),
    ).toEqual([
      {
        type: "text",
        text: "analyze this chart",
      },
      {
        type: "file",
        filename: "chart.png",
        mediaType: "image/png",
      },
    ]);
  });

  test("falls back to experimental attachments when present", () => {
    expect(
      extractNormalizedMessageParts({
        id: "msg-3",
        role: "user",
        content: "",
        experimental_attachments: [
          {
            name: "note.pdf",
            contentType: "application/pdf",
          },
        ],
      } as never),
    ).toEqual([
      {
        type: "file",
        filename: "note.pdf",
        mediaType: "application/pdf",
      },
    ]);
  });
});
