'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useAuth } from './AuthContext';

interface Tenant {
  id: string;
  name: string;
  domain: string;
  schemaName: string;
  isActive: boolean;
  theme?: string;
  primaryColor?: string;
  secondaryColor?: string;
  logo?: string;
  favicon?: string;
  settings?: TenantSettings;
}

interface TenantSettings {
  allowRegistration: boolean;
  requireEmailVerification: boolean;
  maxUsers: number;
  features: string[];
}

interface TenantContextType {
  tenant: Tenant | null;
  isLoading: boolean;
  error: string | null;
  switchTenant: (tenantId: string) => Promise<void>;
  updateTenantSettings: (settings: Partial<TenantSettings>) => Promise<void>;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export const useTenant = () => {
  const context = useContext(TenantContext);
  if (context === undefined) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return context;
};

interface TenantProviderProps {
  children: ReactNode;
}

export const TenantProvider: React.FC<TenantProviderProps> = ({ children }) => {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user, isAuthenticated } = useAuth();

  // TenantContext testing log
  console.log(`🏢 TenantContext: isAuthenticated=${isAuthenticated}, tenant=${tenant?.name || 'null'}, isLoading=${isLoading}`);

  useEffect(() => {
    if (isAuthenticated && user) {
      loadTenantData();
    } else {
      setIsLoading(false);
    }
  }, [isAuthenticated, user]);

  const loadTenantData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = localStorage.getItem('authToken');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/tenants/current/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to load tenant data');
      }

      const tenantData = await response.json();
      setTenant(tenantData);
    } catch (error) {
      console.error('Error loading tenant data:', error);
      setError(error instanceof Error ? error.message : 'Failed to load tenant data');
    } finally {
      setIsLoading(false);
    }
  };

  const switchTenant = async (tenantId: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const token = localStorage.getItem('authToken');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/tenants/switch/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tenant_id: tenantId }),
      });

      if (!response.ok) {
        throw new Error('Failed to switch tenant');
      }

      const newTenantData = await response.json();
      setTenant(newTenantData);
    } catch (error) {
      console.error('Error switching tenant:', error);
      setError(error instanceof Error ? error.message : 'Failed to switch tenant');
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const updateTenantSettings = async (settings: Partial<TenantSettings>) => {
    try {
      setError(null);

      const token = localStorage.getItem('authToken');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/tenants/settings/`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        throw new Error('Failed to update tenant settings');
      }

      const updatedTenantData = await response.json();
      setTenant(updatedTenantData);
    } catch (error) {
      console.error('Error updating tenant settings:', error);
      setError(error instanceof Error ? error.message : 'Failed to update tenant settings');
      throw error;
    }
  };

  const value: TenantContextType = {
    tenant,
    isLoading,
    error,
    switchTenant,
    updateTenantSettings,
  };

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  );
}; 