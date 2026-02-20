"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { webSocketUrl } from "@/lib/vnpy-api";

export interface VnpyFeedMessage {
  topic: string;
  data: unknown;
  receivedAt: number;
}

export function useVnpyFeed(token?: string) {
  const [internalConnected, setInternalConnected] = useState(false);
  const [messages, setMessages] = useState<VnpyFeedMessage[]>([]);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const canConnect = useMemo(() => Boolean(token && token.length > 0), [token]);
  const connected = canConnect && internalConnected;

  useEffect(() => {
    if (!canConnect || !token) {
      return;
    }

    let socket: WebSocket | null = null;
    let shouldReconnect = true;

    const connect = () => {
      socket = new WebSocket(webSocketUrl(token));

      socket.onopen = () => {
        setInternalConnected(true);
      };

      socket.onclose = () => {
        setInternalConnected(false);

        if (shouldReconnect) {
          reconnectTimer.current = setTimeout(connect, 3000);
        }
      };

      socket.onerror = () => {
        socket?.close();
      };

      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as { topic?: string; data?: unknown };
          const next: VnpyFeedMessage = {
            topic: parsed.topic ?? "unknown",
            data: parsed.data,
            receivedAt: Date.now(),
          };

          setMessages((prev) => [next, ...prev].slice(0, 120));
        } catch {
          const next: VnpyFeedMessage = {
            topic: "raw",
            data: event.data,
            receivedAt: Date.now(),
          };

          setMessages((prev) => [next, ...prev].slice(0, 120));
        }
      };
    };

    connect();

    return () => {
      shouldReconnect = false;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      socket?.close();
    };
  }, [canConnect, token]);

  return {
    connected,
    messages,
    latest: messages[0],
  };
}
