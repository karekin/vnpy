'use client';

import { useTenant } from '@/context/TenantContext';

export const useTenantTheme = () => {
  const { tenant } = useTenant();
  
  const getThemeConfig = () => {
    const defaultTheme = {
      primary: 'bg-primary',
      secondary: 'bg-secondary',
      accent: 'bg-accent',
      text: 'text-foreground',
      border: 'border-stroke',
      background: 'bg-white',
      darkBackground: 'dark:bg-boxdark',
      darkBorder: 'dark:border-strokedark',
      darkText: 'dark:text-white'
    };

    if (!tenant?.theme) {
      return defaultTheme;
    }

    // Custom theme based on tenant
    switch (tenant.theme) {
      case 'dark':
        return {
          ...defaultTheme,
          primary: 'bg-gray-800',
          secondary: 'bg-gray-700',
          background: 'bg-gray-900',
          darkBackground: 'dark:bg-gray-900'
        };
      case 'blue':
        return {
          ...defaultTheme,
          primary: 'bg-blue-600',
          secondary: 'bg-blue-500',
          accent: 'bg-blue-400'
        };
      case 'green':
        return {
          ...defaultTheme,
          primary: 'bg-green-600',
          secondary: 'bg-green-500',
          accent: 'bg-green-400'
        };
      case 'purple':
        return {
          ...defaultTheme,
          primary: 'bg-purple-600',
          secondary: 'bg-purple-500',
          accent: 'bg-purple-400'
        };
      default:
        return defaultTheme;
    }
  };

  const getCustomColors = () => {
    if (!tenant) return null;

    return {
      primaryColor: tenant.primaryColor || '#3b82f6',
      secondaryColor: tenant.secondaryColor || '#64748b',
      accentColor: tenant.secondaryColor || '#8b5cf6'
    };
  };

  const applyCustomColors = () => {
    const colors = getCustomColors();
    if (!colors) return;

    // Apply CSS custom properties
    if (typeof document !== 'undefined') {
      document.documentElement.style.setProperty('--primary-color', colors.primaryColor);
      document.documentElement.style.setProperty('--secondary-color', colors.secondaryColor);
      document.documentElement.style.setProperty('--accent-color', colors.accentColor);
    }
  };

  const getTenantLogo = () => {
    return tenant?.logo || '/images/logo/default-logo.svg';
  };

  const getTenantFavicon = () => {
    return tenant?.favicon || '/favicon.ico';
  };

  const getTenantName = () => {
    return tenant?.name || 'Default Tenant';
  };

  const getTenantDomain = () => {
    return tenant?.domain || 'localhost';
  };

  return {
    getThemeConfig,
    getCustomColors,
    applyCustomColors,
    getTenantLogo,
    getTenantFavicon,
    getTenantName,
    getTenantDomain,
    tenant
  };
}; 