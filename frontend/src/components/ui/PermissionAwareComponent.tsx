'use client';

import React from 'react';
import { usePermissions } from '@/context/PermissionContext';

interface PermissionAwareComponentProps {
  permission: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  showFallback?: boolean;
}

export const PermissionAwareComponent: React.FC<PermissionAwareComponentProps> = ({
  permission,
  children,
  fallback = null,
  showFallback = false
}) => {
  const { hasPermission } = usePermissions();

  if (!hasPermission(permission)) {
    return showFallback ? <>{fallback}</> : null;
  }

  return <>{children}</>;
};

interface PermissionAwareButtonProps {
  permission: string;
  children: React.ReactNode;
  className?: string;
  variant?: 'primary' | 'secondary' | 'danger' | 'success';
  size?: 'sm' | 'md' | 'lg';
  onClick?: () => void;
  disabled?: boolean;
  fallback?: React.ReactNode;
  showFallback?: boolean;
}

export const PermissionAwareButton: React.FC<PermissionAwareButtonProps> = ({
  permission,
  children,
  className = '',
  variant = 'primary',
  size = 'md',
  onClick,
  disabled = false,
  fallback = null,
  showFallback = false
}) => {
  const { hasPermission } = usePermissions();

  if (!hasPermission(permission)) {
    return showFallback ? <>{fallback}</> : null;
  }

  const baseClasses = 'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background';
  
  const variantClasses = {
    primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
    secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
    danger: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
    success: 'bg-green-600 text-white hover:bg-green-700'
  };

  const sizeClasses = {
    sm: 'h-9 px-3',
    md: 'h-10 px-4 py-2',
    lg: 'h-11 px-8'
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
};

interface PermissionAwareCardProps {
  permission: string;
  children: React.ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  fallback?: React.ReactNode;
  showFallback?: boolean;
}

export const PermissionAwareCard: React.FC<PermissionAwareCardProps> = ({
  permission,
  children,
  className = '',
  title,
  subtitle,
  fallback = null,
  showFallback = false
}) => {
  const { hasPermission } = usePermissions();

  if (!hasPermission(permission)) {
    return showFallback ? <>{fallback}</> : null;
  }

  return (
    <div className={`rounded-sm border border-stroke bg-white shadow-default dark:border-strokedark dark:bg-boxdark ${className}`}>
      {(title || subtitle) && (
        <div className="border-b border-stroke px-6.5 py-4 dark:border-strokedark">
          {title && <h3 className="font-medium text-black dark:text-white">{title}</h3>}
          {subtitle && <p className="text-sm text-bodydark2">{subtitle}</p>}
        </div>
      )}
      <div className="p-6.5">{children}</div>
    </div>
  );
}; 