import React from "react";

type Tone = "green" | "yellow" | "red" | "blue" | "slate";

type StatusTagProps = {
  label: string;
  tone?: Tone;
};

const toneClassMap: Record<Tone, string> = {
  green:
    "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300",
  yellow:
    "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-300",
  red: "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300",
  blue: "bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-300",
  slate: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

export default function StatusTag({ label, tone = "slate" }: StatusTagProps) {
  return (
    <span
      className={`inline-flex max-w-full break-words rounded-full px-2 py-1 text-center text-xs font-medium leading-tight ${toneClassMap[tone]}`}
    >
      {label}
    </span>
  );
}
