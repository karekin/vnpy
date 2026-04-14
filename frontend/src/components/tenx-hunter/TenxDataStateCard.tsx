import React from "react";

type TenxDataStateCardProps = {
  title: string;
  message: string;
  detail?: string;
  tone?: "error" | "warning";
};

const toneClassMap = {
  error: {
    border: "border-red-200 dark:border-red-500/30",
    background: "bg-red-50 dark:bg-red-500/10",
    title: "text-red-700 dark:text-red-200",
    message: "text-red-600 dark:text-red-100",
    detail: "text-red-500 dark:text-red-200/80",
  },
  warning: {
    border: "border-amber-200 dark:border-amber-500/30",
    background: "bg-amber-50 dark:bg-amber-500/10",
    title: "text-amber-800 dark:text-amber-200",
    message: "text-amber-700 dark:text-amber-100",
    detail: "text-amber-600 dark:text-amber-200/80",
  },
} as const;

export default function TenxDataStateCard({
  title,
  message,
  detail,
  tone = "error",
}: TenxDataStateCardProps) {
  const palette = toneClassMap[tone];

  return (
    <div className={`rounded-2xl border p-5 ${palette.border} ${palette.background}`}>
      <h3 className={`text-lg font-semibold ${palette.title}`}>{title}</h3>
      <p className={`mt-2 text-sm leading-6 ${palette.message}`}>{message}</p>
      {detail ? (
        <p className={`mt-3 break-words rounded-xl bg-white/60 px-3 py-2 text-xs dark:bg-black/10 ${palette.detail}`}>
          {detail}
        </p>
      ) : null}
    </div>
  );
}
