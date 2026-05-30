"use client";

import Link from "next/link";

type BrandLogoProps = {
  compact?: boolean;
  className?: string;
};

function TideMark() {
  return (
    <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] border border-gray-200 bg-white text-brand-600 shadow-[0_8px_22px_rgba(15,23,42,0.08)] dark:border-gray-700 dark:bg-gray-900 dark:text-brand-300">
      <svg
        className="h-8 w-8"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M5.5 19.6C8 16.8 10.6 16.8 13.1 19.6C15.8 22.6 19.1 22.3 22.8 18"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M9 13.8C11 11.7 13.2 11.7 15.2 13.8C17.3 16 19.9 15.8 22.7 12.8"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.72"
        />
        <path
          d="M20.2 7.5H25.5V12.8"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M6.5 24.4H25.5"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          opacity="0.32"
        />
      </svg>
      <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-gray-900" />
    </span>
  );
}

function BrandWordmark() {
  return (
    <span className="relative inline-flex h-10 items-center">
      <span className="relative z-10 bg-[linear-gradient(135deg,#0f172a_0%,#1d4ed8_48%,#06b6d4_100%)] bg-clip-text text-[27px] font-black leading-none tracking-[0] text-transparent drop-shadow-[0_10px_18px_rgba(37,99,235,0.18)] dark:bg-[linear-gradient(135deg,#ffffff_0%,#93c5fd_48%,#67e8f9_100%)]">
        踏潮
      </span>
      <span
        aria-hidden="true"
        className="absolute -bottom-0.5 left-0 h-[3px] w-full rounded-full bg-[linear-gradient(90deg,#2563eb_0%,#22d3ee_100%)] opacity-80 shadow-[0_4px_14px_rgba(37,99,235,0.28)]"
      />
      <span
        aria-hidden="true"
        className="absolute -right-2 top-1 h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_14px_rgba(34,211,238,0.75)]"
      />
    </span>
  );
}

const BrandLogo = ({ compact = false, className = "" }: BrandLogoProps) => {
  return (
    <Link
      href="/tenx-hunter/us"
      aria-label="踏潮"
      className={`inline-flex items-center gap-3 ${className}`}
    >
      <TideMark />
      {!compact && <BrandWordmark />}
    </Link>
  );
};

export default BrandLogo;
