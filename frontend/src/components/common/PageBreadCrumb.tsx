import Link from "next/link";
import React from "react";

interface BreadcrumbProps {
  pageTitle: string;
  action?: React.ReactNode;
  description?: React.ReactNode;
}

const PageBreadcrumb: React.FC<BreadcrumbProps> = ({ pageTitle, action, description }) => {
  return (
    <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <h2
          className="text-xl font-semibold text-gray-800 dark:text-white/90"
          x-text="pageName"
        >
          {pageTitle}
        </h2>
        {description ? (
          <p className="mt-1 max-w-4xl text-sm leading-6 text-gray-500 dark:text-gray-400">
            {description}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-start gap-3 lg:justify-end">
        <nav>
          <ol className="flex items-center gap-1.5">
            <li>
              <Link
                className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400"
                href="/"
              >
                Home
                <svg
                  className="stroke-current"
                  width="17"
                  height="16"
                  viewBox="0 0 17 16"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M6.0765 12.667L10.2432 8.50033L6.0765 4.33366"
                    stroke=""
                    strokeWidth="1.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </Link>
            </li>
            <li className="text-sm text-gray-800 dark:text-white/90">
              {pageTitle}
            </li>
          </ol>
        </nav>
        {action}
      </div>
    </div>
  );
};

export default PageBreadcrumb;
