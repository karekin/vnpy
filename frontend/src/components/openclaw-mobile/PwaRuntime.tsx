"use client";

import { useEffect } from "react";

export default function PwaRuntime() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) {
      return;
    }

    if (process.env.NODE_ENV !== "production") {
      const clearDevServiceWorkers = async () => {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map((registration) => registration.unregister()));
        if ("caches" in window) {
          const cacheNames = await caches.keys();
          await Promise.all(cacheNames.map((cacheName) => caches.delete(cacheName)));
        }
      };

      clearDevServiceWorkers().catch((error) => {
        console.warn("OpenClaw service worker cleanup failed", error);
      });
      return;
    }

    const register = async () => {
      try {
        await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      } catch (error) {
        console.warn("OpenClaw service worker registration failed", error);
      }
    };

    register();
  }, []);

  return null;
}
