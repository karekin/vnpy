'use client';

import React from 'react';
import { usePermissions } from '@/context/PermissionContext';

interface NavigationItem {
  name: string;
  path: string;
  icon?: React.ReactNode;
  permission?: string;
  subItems?: NavigationItem[];
  new?: boolean;
  pro?: boolean;
}

interface PermissionAwareNavigationProps {
  items: NavigationItem[];
  className?: string;
  renderItem: (item: NavigationItem, index: number) => React.ReactNode;
}

export const PermissionAwareNavigation: React.FC<PermissionAwareNavigationProps> = ({
  items,
  className = '',
  renderItem
}) => {
  const { hasPermission } = usePermissions();

  const filterItemsByPermission = (items: NavigationItem[]): NavigationItem[] => {
    return items.filter(item => {
      // If no permission required, show item
      if (!item.permission) {
        return true;
      }

      // Check if user has permission
      if (!hasPermission(item.permission)) {
        return false;
      }

      // If item has sub-items, filter them too
      if (item.subItems) {
        const filteredSubItems = filterItemsByPermission(item.subItems);
        if (filteredSubItems.length === 0) {
          return false; // Hide parent if no sub-items are accessible
        }
        item.subItems = filteredSubItems;
      }

      return true;
    });
  };

  const filteredItems = filterItemsByPermission(items);

  return (
    <div className={className}>
      {filteredItems.map((item, index) => renderItem(item, index))}
    </div>
  );
};

interface NavigationSectionProps {
  title: string;
  items: NavigationItem[];
  className?: string;
  renderItem: (item: NavigationItem, index: number) => React.ReactNode;
}

export const NavigationSection: React.FC<NavigationSectionProps> = ({
  title,
  items,
  className = '',
  renderItem
}) => {
  const { hasPermission } = usePermissions();

  const filterItemsByPermission = (items: NavigationItem[]): NavigationItem[] => {
    return items.filter(item => {
      if (!item.permission) return true;
      return hasPermission(item.permission);
    });
  };

  const filteredItems = filterItemsByPermission(items);

  if (filteredItems.length === 0) {
    return null; // Don't render section if no items are accessible
  }

  return (
    <div className={className}>
      <h3 className="text-sm font-medium text-bodydark2 mb-2">{title}</h3>
      {filteredItems.map((item, index) => renderItem(item, index))}
    </div>
  );
};

// Predefined navigation items with permissions
export const getNavigationItems = (): NavigationItem[] => [
  {
    name: 'Dashboard',
    path: '/',
    permission: 'dashboard.view',
    subItems: [
      { name: 'Overview', path: '/', permission: 'dashboard.view' },
      { name: 'Analytics', path: '/analytics', permission: 'analytics.view' },
      { name: 'Reports', path: '/reports', permission: 'reports.view' }
    ]
  },
  {
    name: 'Users',
    path: '/users',
    permission: 'user.view',
    subItems: [
      { name: 'User List', path: '/users', permission: 'user.view' },
      { name: 'Add User', path: '/users/add', permission: 'user.create' },
      { name: 'User Roles', path: '/users/roles', permission: 'role.view' }
    ]
  },
  {
    name: 'Settings',
    path: '/settings',
    permission: 'settings.view',
    subItems: [
      { name: 'General', path: '/settings/general', permission: 'settings.view' },
      { name: 'Security', path: '/settings/security', permission: 'settings.security' },
      { name: 'Tenant', path: '/settings/tenant', permission: 'settings.tenant' }
    ]
  },
  {
    name: 'System',
    path: '/system',
    permission: 'system.view',
    subItems: [
      { name: 'Logs', path: '/system/logs', permission: 'system.logs' },
      { name: 'Backups', path: '/system/backups', permission: 'system.backups' },
      { name: 'Monitoring', path: '/system/monitoring', permission: 'system.monitoring' }
    ]
  }
];

// Hook for getting filtered navigation items
export const useFilteredNavigation = () => {
  const { hasPermission } = usePermissions();
  
  const filterItems = (items: NavigationItem[]): NavigationItem[] => {
    return items.filter(item => {
      if (!item.permission) return true;
      return hasPermission(item.permission);
    });
  };

  return { filterItems };
}; 