'use client';

import React, { useEffect } from 'react';
import Image from 'next/image';
import { useTenantTheme } from '@/hooks/useTenantTheme';

interface TenantThemeProviderProps {
  children: React.ReactNode;
}

export const TenantThemeProvider: React.FC<TenantThemeProviderProps> = ({ children }) => {
  const { applyCustomColors, getTenantFavicon, getTenantName, tenant } = useTenantTheme();

  useEffect(() => {
    // Apply custom colors when tenant changes
    applyCustomColors();

    // Update favicon if tenant has custom favicon
    const favicon = getTenantFavicon();
    if (favicon && typeof document !== 'undefined') {
      const link = document.querySelector("link[rel*='icon']") as HTMLLinkElement;
      if (link) {
        link.href = favicon;
      } else {
        const newLink = document.createElement('link');
        newLink.rel = 'icon';
        newLink.href = favicon;
        document.head.appendChild(newLink);
      }
    }

    // Update page title with tenant name
    const tenantName = getTenantName();
    if (tenantName && typeof document !== 'undefined') {
      const currentTitle = document.title;
      if (!currentTitle.includes(tenantName)) {
        document.title = `${tenantName} - ${currentTitle}`;
      }
    }
  }, [tenant, applyCustomColors, getTenantFavicon, getTenantName]);

  return <>{children}</>;
};

interface TenantBrandingProps {
  className?: string;
  showLogo?: boolean;
  showName?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const TenantBranding: React.FC<TenantBrandingProps> = ({
  className = '',
  showLogo = true,
  showName = true,
  size = 'md'
}) => {
  const { getTenantLogo, getTenantName } = useTenantTheme();

  const sizeClasses = {
    sm: 'h-6',
    md: 'h-8',
    lg: 'h-12'
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {showLogo && (
        <Image
          src={getTenantLogo()}
          alt={`${getTenantName()} logo`}
          width={size === 'sm' ? 24 : size === 'md' ? 32 : 48}
          height={size === 'sm' ? 24 : size === 'md' ? 32 : 48}
          className={`${sizeClasses[size]} w-auto`}
        />
      )}
      {showName && (
        <span className="font-semibold text-lg">{getTenantName()}</span>
      )}
    </div>
  );
}; 