"use client";
import React, { useEffect, useRef, useCallback, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSidebar } from "../context/SidebarContext";
import {
  AiIcon,
  ChevronDownIcon,
  DocsIcon,
  HorizontaLDots,
  PieChartIcon,
} from "../icons/index";
import BrandLogo from "./BrandLogo";

type NavItem = {
  name: string;
  icon: React.ReactNode;
  path?: string;
  subItems?: { name: string; path: string }[];
};

const navItems: NavItem[] = [
  {
    name: "Investment Copilot",
    icon: <AiIcon />,
    path: "/investment-copilot",
  },
  {
    name: "TenX Hunter",
    icon: <AiIcon />,
    subItems: [
      { name: "Workspace", path: "/tenx-hunter/us" },
      { name: "Hot Monitor", path: "/tenx-hunter/us/hot-monitor" },
      { name: "Discover", path: "/tenx-hunter/us/discover" },
      { name: "Watchlist", path: "/tenx-hunter/us/watchlist" },
      { name: "Alerts", path: "/tenx-hunter/us/alerts" },
      { name: "Themes", path: "/tenx-hunter/us/themes" },
      { name: "Sentiment", path: "/tenx-hunter/us/sentiment" },
      { name: "Political Signals", path: "/tenx-hunter/us/political-signals" },
    ],
  },
  {
    name: "Smart Allocation",
    icon: <PieChartIcon />,
    subItems: [
      { name: "Account Targets", path: "/smart-allocation" },
      { name: "Cash Waterfall", path: "/smart-allocation/waterfall" },
      { name: "Rebalance", path: "/smart-allocation/rebalance" },
      { name: "LEAPS Candidates", path: "/smart-allocation/leaps" },
      { name: "Options Strategies", path: "/smart-allocation/options-strategies" },
      { name: "Risk Guardrails", path: "/smart-allocation/guardrails" },
      { name: "Quarterly Review", path: "/smart-allocation/review" },
    ],
  },
  {
    name: "CB Quant",
    icon: <DocsIcon />,
    subItems: [
      { name: "Overview", path: "/cb-quant" },
      { name: "Info Mining", path: "/cb-quant/info-mining" },
      { name: "Strategy Generation", path: "/cb-quant/strategy-generation" },
      { name: "Backtest Evaluation", path: "/cb-quant/backtest-evaluation" },
      { name: "Auto Execution", path: "/cb-quant/auto-execution" },
      { name: "Review", path: "/cb-quant/review" },
      { name: "Continuous Iteration", path: "/cb-quant/continuous-iteration" },
    ],
  },
];

const AppSidebar: React.FC = () => {
  const { isExpanded, isMobileOpen, isHovered, setIsHovered } = useSidebar();
  const pathname = usePathname();

  const [openSubmenu, setOpenSubmenu] = useState<{
    type: "main";
    index: number;
  } | null>(null);
  const [, setSubMenuHeight] = useState<Record<string, number>>({});
  const subMenuRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const renderMenuItems = (
    navItems: NavItem[],
    menuType: "main"
  ) => (
    <ul className="flex flex-col gap-1">
      {navItems.map((nav, index) => (
        <li key={nav.name}>
          {nav.subItems ? (
            <button
              onClick={() => handleSubmenuToggle(index, menuType)}
              className={`menu-item group  ${
                openSubmenu?.type === menuType && openSubmenu?.index === index
                  ? "menu-item-active"
                  : "menu-item-inactive"
              } cursor-pointer ${
                !isExpanded && !isHovered
                  ? "lg:justify-center"
                  : "lg:justify-start"
              }`}
            >
              <span
                className={` ${
                  openSubmenu?.type === menuType && openSubmenu?.index === index
                    ? "menu-item-icon-active"
                    : "menu-item-icon-inactive"
                }`}
              >
                {nav.icon}
              </span>
              {(isExpanded || isHovered || isMobileOpen) && (
                <span className={`menu-item-text`}>{nav.name}</span>
              )}
              {(isExpanded || isHovered || isMobileOpen) && (
                <ChevronDownIcon
                  className={`ml-auto w-5 h-5 transition-transform duration-200  ${
                    openSubmenu?.type === menuType &&
                    openSubmenu?.index === index
                      ? "rotate-180 text-brand-500"
                      : ""
                  }`}
                />
              )}
            </button>
          ) : (
            nav.path && (
              <Link
                href={nav.path}
                className={`menu-item group ${
                  isActive(nav.path) ? "menu-item-active" : "menu-item-inactive"
                }`}
              >
                <span
                  className={`${
                    isActive(nav.path)
                      ? "menu-item-icon-active"
                      : "menu-item-icon-inactive"
                  }`}
                >
                  {nav.icon}
                </span>
                {(isExpanded || isHovered || isMobileOpen) && (
                  <span className={`menu-item-text`}>{nav.name}</span>
                )}
              </Link>
            )
          )}
          {nav.subItems && (isExpanded || isHovered || isMobileOpen) && (
            <div
              ref={(el) => {
                subMenuRefs.current[`${menuType}-${index}`] = el;
              }}
              className={`transition-all duration-300 ${
                openSubmenu?.type === menuType && openSubmenu?.index === index
                  ? "block"
                  : "hidden"
              }`}
            >
              <ul className="mt-2 space-y-1 ml-9">
                {nav.subItems.map((subItem) => (
                  <li key={subItem.name}>
                    <Link
                      href={subItem.path}
                      className={`menu-dropdown-item ${
                        isActive(subItem.path)
                          ? "menu-dropdown-item-active"
                          : "menu-dropdown-item-inactive"
                      }`}
                    >
                      {subItem.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </li>
      ))}
    </ul>
  );

  const isActive = useCallback((path: string) => path === pathname, [pathname]);

  useEffect(() => {
    let submenuMatched = false;

    navItems.forEach((nav, index) => {
      nav.subItems?.forEach((subItem) => {
        if (isActive(subItem.path)) {
          setOpenSubmenu({
            type: "main",
            index,
          });
          submenuMatched = true;
        }
      });
    });

    if (!submenuMatched) {
      setOpenSubmenu(null);
    }
  }, [pathname, isActive]);

  useEffect(() => {
    if (openSubmenu !== null) {
      const key = `${openSubmenu.type}-${openSubmenu.index}`;
      if (subMenuRefs.current[key]) {
        const scrollHeight = subMenuRefs.current[key]?.scrollHeight || 0;
        setSubMenuHeight((prevHeights) => ({
          ...prevHeights,
          [key]: scrollHeight,
        }));
      }
    }
  }, [openSubmenu]);

  const handleSubmenuToggle = (
    index: number,
    menuType: "main"
  ) => {
    setOpenSubmenu((prevOpenSubmenu) => {
      if (
        prevOpenSubmenu &&
        prevOpenSubmenu.type === menuType &&
        prevOpenSubmenu.index === index
      ) {
        return null;
      }
      return { type: menuType, index };
    });
  };

  return (
    <aside
      className={`fixed  flex flex-col xl:mt-0 top-0 px-5 left-0 bg-white dark:bg-gray-900 dark:border-gray-800 text-gray-900 h-full transition-all duration-300 ease-in-out z-50 border-r border-gray-200 
        ${
          isExpanded || isMobileOpen
            ? "w-[290px]"
            : isHovered
            ? "w-[290px]"
            : "w-[90px]"
        }
        ${isMobileOpen ? "translate-x-0" : "-translate-x-full"}
        xl:translate-x-0`}
      onMouseEnter={() => !isExpanded && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        className={`py-8 flex  ${
          !isExpanded && !isHovered ? "xl:justify-center" : "justify-start"
        }`}
      >
        <BrandLogo compact={!(isExpanded || isHovered || isMobileOpen)} />
      </div>
      <div className="flex flex-col overflow-y-auto  duration-300 ease-linear no-scrollbar">
        <nav className="mb-6">
          <div className="flex flex-col gap-4">
            <div>
              <h2
                className={`mb-4 text-xs uppercase flex leading-5 text-gray-400 ${
                  !isExpanded && !isHovered
                    ? "xl:justify-center"
                    : "justify-start"
                }`}
              >
                {isExpanded || isHovered || isMobileOpen ? (
                  "Menu"
                ) : (
                  <HorizontaLDots />
                )}
              </h2>
              {renderMenuItems(navItems, "main")}
            </div>
          </div>
        </nav>
      </div>
    </aside>
  );
};

export default AppSidebar;
