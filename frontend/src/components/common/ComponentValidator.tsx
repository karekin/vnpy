import React from 'react';

// Component validation system to enforce TailAdmin-only usage
export const ComponentValidator = {
  // Allowed TailAdmin components
  allowedComponents: {
    // Layout components
    'ComponentCard': true,
    'PageBreadcrumb': true,
    
    // UI components
    'Button': true,
    'Input': true,
    'Checkbox': true,
    'Badge': true,
    'Table': true,
    'TableCell': true,
    'TableHeader': true,
    'TableBody': true,
    'TableRow': true,
    
    // Form components
    'Select': true,
    'Textarea': true,
    'Radio': true,
    'Switch': true,
    
    // Navigation components
    'Pagination': true,
    'Breadcrumb': true,
    
    // Feedback components
    'Alert': true,
    'Modal': true,
    'Tooltip': true,
    'Popover': true,
    
    // Data display components
    'Card': true,
    'List': true,
    'Timeline': true,
    'Stats': true,
  },

  // Forbidden custom styling classes
  forbiddenClasses: [
    'bg-gray-',
    'text-gray-',
    'border-gray-',
    'hover:bg-gray-',
    'hover:text-gray-',
    'hover:border-gray-',
    'rounded-md',
    'rounded-lg',
    'px-',
    'py-',
    'p-',
    'm-',
    'mx-',
    'my-',
    'w-',
    'h-',
    'flex',
    'grid',
    'space-y-',
    'gap-',
  ],

  // Validate component usage
  validateComponent: (componentName: string): boolean => {
    return ComponentValidator.allowedComponents[componentName as keyof typeof ComponentValidator.allowedComponents] || false;
  },

  // Validate styling classes
  validateClasses: (className: string): string[] => {
    const violations: string[] = [];
    ComponentValidator.forbiddenClasses.forEach(forbidden => {
      if (className.includes(forbidden)) {
        violations.push(`Forbidden class: ${forbidden}`);
      }
    });
    return violations;
  },

  // Get component import path
  getComponentPath: (componentName: string): string => {
    const paths: Record<string, string> = {
      'ComponentCard': '@/components/common/ComponentCard',
      'PageBreadcrumb': '@/components/common/PageBreadCrumb',
      'Button': '@/components/ui/button/Button',
      'Input': '@/components/form/input/InputField',
      'Checkbox': '@/components/form/input/Checkbox',
      'Badge': '@/components/ui/badge/Badge',
      'Table': '@/components/ui/table',
      'Select': '@/components/ui/select/Select',
    };
    return paths[componentName] || '';
  }
};

// React component wrapper for validation
export const ValidatedComponent: React.FC<{
  component: React.ComponentType<Record<string, unknown>>;
  props: Record<string, unknown>;
  componentName: string;
}> = ({ component: Component, props, componentName }) => {
  if (!ComponentValidator.validateComponent(componentName)) {
    console.error(`❌ INVALID COMPONENT: ${componentName} is not a TailAdmin component!`);
    console.error(`✅ Use one of these instead:`, Object.keys(ComponentValidator.allowedComponents));
    return null;
  }

  // Validate className if present
  if (props.className && typeof props.className === 'string') {
    const violations = ComponentValidator.validateClasses(props.className);
    if (violations.length > 0) {
      console.error(`❌ FORBIDDEN STYLING in ${componentName}:`, violations);
      console.error(`✅ Use TailAdmin's built-in styling instead`);
    }
  }

  return <Component {...props} />;
};

export default ComponentValidator; 