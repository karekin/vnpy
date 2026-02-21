import React from 'react';
import { render, screen } from '@testing-library/react';
import { PermissionAwareComponent, PermissionAwareButton, PermissionAwareCard } from '../ui/PermissionAwareComponent';

// Mock the contexts
jest.mock('@/context/PermissionContext', () => ({
  usePermissions: jest.fn()
}));

jest.mock('@/context/AuthContext', () => ({
  useAuth: jest.fn()
}));

jest.mock('@/context/TenantContext', () => ({
  useTenant: jest.fn()
}));

import { usePermissions } from '@/context/PermissionContext';

// Mock the permission context
const mockUsePermissions = usePermissions as jest.MockedFunction<typeof usePermissions>;

describe('PermissionAwareComponent', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders children when user has permission', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(true),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareComponent permission="user.view">
        <div data-testid="test-content">Test Content</div>
      </PermissionAwareComponent>
    );
    
    expect(screen.getByTestId('test-content')).toBeInTheDocument();
  });

  test('does not render when user lacks permission', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(false),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareComponent permission="admin.access">
        <div data-testid="test-content">Test Content</div>
      </PermissionAwareComponent>
    );
    
    expect(screen.queryByTestId('test-content')).not.toBeInTheDocument();
  });

  test('renders fallback when user lacks permission and showFallback is true', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(false),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareComponent 
        permission="admin.access" 
        fallback={<div data-testid="fallback">Access Denied</div>}
        showFallback={true}
      >
        <div data-testid="test-content">Test Content</div>
      </PermissionAwareComponent>
    );
    
    expect(screen.getByTestId('fallback')).toBeInTheDocument();
    expect(screen.queryByTestId('test-content')).not.toBeInTheDocument();
  });
});

describe('PermissionAwareButton', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders button when user has permission', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(true),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareButton permission="user.create">
        Create User
      </PermissionAwareButton>
    );
    
    expect(screen.getByText('Create User')).toBeInTheDocument();
  });

  test('does not render button when user lacks permission', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(false),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareButton permission="admin.access">
        Admin Action
      </PermissionAwareButton>
    );
    
    expect(screen.queryByText('Admin Action')).not.toBeInTheDocument();
  });

  test('applies correct variant classes', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(true),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareButton permission="user.create" variant="danger">
        Delete User
      </PermissionAwareButton>
    );
    
    const button = screen.getByText('Delete User');
    expect(button).toHaveClass('bg-destructive');
  });
});

describe('PermissionAwareCard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders card when user has permission', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(true),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareCard permission="user.view" title="User Management">
        <div data-testid="card-content">Card content</div>
      </PermissionAwareCard>
    );
    
    expect(screen.getByText('User Management')).toBeInTheDocument();
    expect(screen.getByTestId('card-content')).toBeInTheDocument();
  });

  test('does not render card when user lacks permission', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(false),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareCard permission="admin.access" title="Admin Panel">
        <div data-testid="card-content">Admin content</div>
      </PermissionAwareCard>
    );
    
    expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('card-content')).not.toBeInTheDocument();
  });

  test('renders card with subtitle', () => {
    mockUsePermissions.mockReturnValue({
      hasPermission: jest.fn().mockReturnValue(true),
      hasRole: jest.fn(),
      hasAnyPermission: jest.fn(),
      hasAllPermissions: jest.fn(),
      permissions: [],
      roles: [],
      userRoles: [],
      isLoading: false,
      error: null,
      refreshPermissions: jest.fn()
    });

    render(
      <PermissionAwareCard 
        permission="user.view" 
        title="User Management"
        subtitle="Manage user accounts and permissions"
      >
        <div data-testid="card-content">Card content</div>
      </PermissionAwareCard>
    );
    
    expect(screen.getByText('User Management')).toBeInTheDocument();
    expect(screen.getByText('Manage user accounts and permissions')).toBeInTheDocument();
  });
}); 