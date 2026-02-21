'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { useTenant } from './TenantContext';

interface Permission {
  id: string;
  name: string;
  codename: string;
  contentType: string;
}

interface Role {
  id: string;
  name: string;
  permissions: Permission[];
}

interface UserRole {
  id: string;
  user: string;
  role: Role;
  tenant: string;
}

interface PermissionContextType {
  permissions: Permission[];
  roles: Role[];
  userRoles: UserRole[];
  isLoading: boolean;
  error: string | null;
  hasPermission: (permission: string) => boolean;
  hasRole: (roleName: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
  refreshPermissions: () => Promise<void>;
}

const PermissionContext = createContext<PermissionContextType | undefined>(undefined);

export const usePermissions = () => {
  const context = useContext(PermissionContext);
  if (context === undefined) {
    throw new Error('usePermissions must be used within a PermissionProvider');
  }
  return context;
};

interface PermissionProviderProps {
  children: ReactNode;
}

export const PermissionProvider: React.FC<PermissionProviderProps> = ({ children }) => {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [userRoles, setUserRoles] = useState<UserRole[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { user, isAuthenticated } = useAuth();
  const { tenant } = useTenant();

  // PermissionContext testing log
  console.log(`🔑 PermissionContext: isAuthenticated=${isAuthenticated}, permissions=${permissions.length}, roles=${roles.length}`);

  useEffect(() => {
    if (isAuthenticated && user && tenant) {
      loadUserPermissions();
    } else {
      setIsLoading(false);
    }
  }, [isAuthenticated, user, tenant]);

  const loadUserPermissions = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = localStorage.getItem('authToken');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Load user roles and permissions
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/permissions/user/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to load user permissions');
      }

      const data = await response.json();
      setUserRoles(data.user_roles || []);
      setPermissions(data.permissions || []);
      setRoles(data.roles || []);
    } catch (error) {
      console.error('Error loading user permissions:', error);
      setError(error instanceof Error ? error.message : 'Failed to load user permissions');
    } finally {
      setIsLoading(false);
    }
  };

  const hasPermission = (permission: string): boolean => {
    if (!userRoles.length) return false;
    
    return userRoles.some(userRole => 
      userRole.role.permissions.some(perm => 
        perm.codename === permission || perm.codename === '*'
      )
    );
  };

  const hasRole = (roleName: string): boolean => {
    if (!userRoles.length) return false;
    
    return userRoles.some(userRole => 
      userRole.role.name === roleName || userRole.role.name === 'superuser'
    );
  };

  const hasAnyPermission = (permissions: string[]): boolean => {
    return permissions.some(permission => hasPermission(permission));
  };

  const hasAllPermissions = (permissions: string[]): boolean => {
    return permissions.every(permission => hasPermission(permission));
  };

  const refreshPermissions = async () => {
    await loadUserPermissions();
  };

  const value: PermissionContextType = {
    permissions,
    roles,
    userRoles,
    isLoading,
    error,
    hasPermission,
    hasRole,
    hasAnyPermission,
    hasAllPermissions,
    refreshPermissions,
  };

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
}; 