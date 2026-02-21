import React, { useMemo } from "react";

type TablePaginationBarProps = {
  totalItems: number;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
};

const buildVisiblePages = (currentPage: number, totalPages: number): number[] => {
  const maxVisible = 5;
  let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
  const end = Math.min(totalPages, start + maxVisible - 1);
  if (end - start + 1 < maxVisible) {
    start = Math.max(1, end - maxVisible + 1);
  }
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
};

export default function TablePaginationBar({
  totalItems,
  currentPage,
  totalPages,
  onPageChange,
}: TablePaginationBarProps) {
  const visiblePages = useMemo(
    () => buildVisiblePages(currentPage, totalPages),
    [currentPage, totalPages]
  );

  return (
    <div className="mt-4 flex flex-col items-center justify-between border-t border-gray-200 px-1 py-4 sm:flex-row dark:border-gray-800">
      <div className="pb-4 sm:pb-0">
        <span className="block text-sm font-medium text-gray-500 dark:text-gray-400">
          共 <span className="text-gray-800 dark:text-white/90">{totalItems}</span> 条，当前第{" "}
          <span className="text-gray-800 dark:text-white/90">{currentPage}</span> /{" "}
          <span className="text-gray-800 dark:text-white/90">{totalPages}</span> 页
        </span>
      </div>
      <div className="flex w-full items-center justify-between gap-2 rounded-lg bg-gray-50 p-4 sm:w-auto sm:justify-normal sm:bg-transparent sm:p-0 dark:bg-white/[0.03] dark:sm:bg-transparent">
        <button
          className={`shadow-theme-xs flex items-center gap-2 rounded-lg border border-gray-300 bg-white p-2 text-gray-700 hover:bg-gray-50 hover:text-gray-800 sm:p-2.5 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/[0.03] dark:hover:text-gray-200 ${
            currentPage === 1 ? "cursor-not-allowed opacity-50" : ""
          }`}
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
        >
          <svg className="fill-current" width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M2.58203 9.99868C2.58174 10.1909 2.6549 10.3833 2.80152 10.53L7.79818 15.5301C8.09097 15.8231 8.56584 15.8233 8.85883 15.5305C9.15183 15.2377 9.152 14.7629 8.85921 14.4699L5.13911 10.7472L16.6665 10.7472C17.0807 10.7472 17.4165 10.4114 17.4165 9.99715C17.4165 9.58294 17.0807 9.24715 16.6665 9.24715L5.14456 9.24715L8.85919 5.53016C9.15199 5.23717 9.15184 4.7623 8.85885 4.4695C8.56587 4.1767 8.09099 4.17685 7.79819 4.46984L2.84069 9.43049C2.68224 9.568 2.58203 9.77087 2.58203 9.99715C2.58203 9.99766 2.58203 9.99817 2.58203 9.99868Z"
              fill=""
            />
          </svg>
        </button>
        <span className="block text-sm font-medium text-gray-700 sm:hidden dark:text-gray-400">
          Page {currentPage} of {totalPages}
        </span>
        <ul className="hidden items-center gap-0.5 sm:flex">
          {visiblePages.map((page) => (
            <li key={page}>
              <button
                onClick={() => onPageChange(page)}
                className={`flex h-10 w-10 items-center justify-center rounded-lg text-sm font-medium ${
                  page === currentPage
                    ? "bg-brand-500 text-white"
                    : "text-gray-700 hover:bg-brand-500 hover:text-white dark:text-gray-400 dark:hover:text-white"
                }`}
              >
                {page}
              </button>
            </li>
          ))}
          {visiblePages[visiblePages.length - 1] < totalPages && (
            <>
              <li>
                <span className="flex h-10 w-10 items-center justify-center rounded-lg text-sm font-medium text-gray-700 dark:text-gray-400">
                  ...
                </span>
              </li>
              <li>
                <button
                  onClick={() => onPageChange(totalPages)}
                  className="flex h-10 w-10 items-center justify-center rounded-lg text-sm font-medium text-gray-700 hover:bg-brand-500 hover:text-white dark:text-gray-400 dark:hover:text-white"
                >
                  {totalPages}
                </button>
              </li>
            </>
          )}
        </ul>
        <button
          className={`shadow-theme-xs flex items-center gap-2 rounded-lg border border-gray-300 bg-white p-2 text-gray-700 hover:bg-gray-50 hover:text-gray-800 sm:p-2.5 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/[0.03] dark:hover:text-gray-200 ${
            currentPage === totalPages ? "cursor-not-allowed opacity-50" : ""
          }`}
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
        >
          <svg className="fill-current" width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M17.4165 9.9986C17.4168 10.1909 17.3437 10.3832 17.197 10.53L12.2004 15.5301C11.9076 15.8231 11.4327 15.8233 11.1397 15.5305C10.8467 15.2377 10.8465 14.7629 11.1393 14.4699L14.8594 10.7472L3.33203 10.7472C2.91782 10.7472 2.58203 10.4114 2.58203 9.99715C2.58203 9.58294 2.91782 9.24715 3.33203 9.24715L14.854 9.24715L11.1393 5.53016C10.8465 5.23717 10.8467 4.7623 11.1397 4.4695C11.4327 4.1767 11.9075 4.17685 12.2003 4.46984L17.1578 9.43049C17.3163 9.568 17.4165 9.77087 17.4165 9.99715C17.4165 9.99763 17.4165 9.99812 17.4165 9.9986Z"
              fill=""
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
