"use client";

import Link from "next/link";

type BrandLogoProps = {
  compact?: boolean;
  className?: string;
};

const BrandLogo = ({ compact = false, className = "" }: BrandLogoProps) => {
  return (
    <Link
      href="/tenx-hunter/us"
      aria-label="踏潮"
      className={`inline-flex items-center gap-3 ${className}`}
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-500 text-white shadow-theme-xs">
        <svg
          width="26"
          height="26"
          viewBox="0 0 26 26"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M3 15.6C5.5 12.4 8.3 12.4 10.8 15.6C13.4 19 16.6 19 20 14.9"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M15.4 8.3H22V14.9"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M4 20.8H22"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
        </svg>
      </span>
      {!compact && (
        <span className="text-2xl font-semibold tracking-normal text-gray-900 dark:text-white">
          踏潮
        </span>
      )}
    </Link>
  );
};

export default BrandLogo;
