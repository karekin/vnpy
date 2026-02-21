'use client';

import React from 'react';
import clsx from 'clsx';

interface ResponsiveContainerProps {
  children: React.ReactNode;
  className?: string;
  mobile?: string;
  tablet?: string;
  desktop?: string;
  large?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  maxWidth?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full';
}

export const ResponsiveContainer: React.FC<ResponsiveContainerProps> = ({
  children,
  className = '',
  mobile = 'w-full',
  tablet = 'md:w-3/4',
  desktop = 'lg:w-2/3',
  large = 'xl:w-1/2',
  padding = 'md',
  maxWidth = 'none'
}) => {
  const paddingClasses = {
    none: '',
    sm: 'p-2',
    md: 'p-4',
    lg: 'p-6'
  };

  const maxWidthClasses = {
    none: '',
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    full: 'max-w-full'
  };

  return (
    <div className={clsx(
      mobile,
      tablet,
      desktop,
      large,
      paddingClasses[padding],
      maxWidthClasses[maxWidth],
      className
    )}>
      {children}
    </div>
  );
};

interface ResponsiveGridProps {
  children: React.ReactNode;
  className?: string;
  cols?: {
    mobile?: number;
    tablet?: number;
    desktop?: number;
    large?: number;
  };
  gap?: 'none' | 'sm' | 'md' | 'lg';
}

export const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
  children,
  className = '',
  cols = { mobile: 1, tablet: 2, desktop: 3, large: 4 },
  gap = 'md'
}) => {
  const gapClasses = {
    none: '',
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6'
  };

  const gridCols = {
    mobile: `grid-cols-${cols.mobile || 1}`,
    tablet: `md:grid-cols-${cols.tablet || 2}`,
    desktop: `lg:grid-cols-${cols.desktop || 3}`,
    large: `xl:grid-cols-${cols.large || 4}`
  };

  return (
    <div className={clsx(
      'grid',
      gridCols.mobile,
      gridCols.tablet,
      gridCols.desktop,
      gridCols.large,
      gapClasses[gap],
      className
    )}>
      {children}
    </div>
  );
};

interface ResponsiveTableProps {
  children: React.ReactNode;
  className?: string;
  striped?: boolean;
  hover?: boolean;
  bordered?: boolean;
}

export const ResponsiveTable: React.FC<ResponsiveTableProps> = ({
  children,
  className = '',
  striped = false,
  hover = true,
  bordered = false
}) => {
  return (
    <div className={clsx('w-full overflow-x-auto', className)}>
      <table className={clsx(
        'w-full table-auto',
        striped && 'divide-y divide-gray-200',
        hover && 'hover:bg-gray-50',
        bordered && 'border border-gray-200'
      )}>
        {children}
      </table>
    </div>
  );
};

interface ResponsiveCardProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  shadow?: 'none' | 'sm' | 'md' | 'lg';
}

export const ResponsiveCard: React.FC<ResponsiveCardProps> = ({
  children,
  className = '',
  title,
  subtitle,
  padding = 'md',
  shadow = 'md'
}) => {
  const paddingClasses = {
    none: '',
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6'
  };

  const shadowClasses = {
    none: '',
    sm: 'shadow-sm',
    md: 'shadow-md',
    lg: 'shadow-lg'
  };

  return (
    <div className={clsx(
      'rounded-sm border border-stroke bg-white dark:border-strokedark dark:bg-boxdark',
      shadowClasses[shadow],
      className
    )}>
      {(title || subtitle) && (
        <div className="border-b border-stroke px-6.5 py-4 dark:border-strokedark">
          {title && <h3 className="font-medium text-black dark:text-white">{title}</h3>}
          {subtitle && <p className="text-sm text-bodydark2">{subtitle}</p>}
        </div>
      )}
      <div className={paddingClasses[padding]}>{children}</div>
    </div>
  );
}; 