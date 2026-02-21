import React from 'react';
import { render, screen } from '@testing-library/react';
import { AccessibleButton, AccessibleLinkButton, AccessibleIconButton } from '../ui/AccessibleButton';

describe('AccessibleButton', () => {
  test('renders button with children', () => {
    render(
      <AccessibleButton>
        Click me
      </AccessibleButton>
    );
    
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  test('applies aria-label', () => {
    render(
      <AccessibleButton aria-label="Submit form">
        Submit
      </AccessibleButton>
    );
    
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-label', 'Submit form');
  });

  test('applies aria-describedby', () => {
    render(
      <AccessibleButton aria-describedby="help-text">
        Submit
      </AccessibleButton>
    );
    
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-describedby', 'help-text');
  });

  test('applies variant classes', () => {
    render(
      <AccessibleButton variant="danger">
        Delete
      </AccessibleButton>
    );
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-destructive');
  });

  test('applies size classes', () => {
    render(
      <AccessibleButton size="lg">
        Large Button
      </AccessibleButton>
    );
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('h-11', 'px-8');
  });

  test('handles click events', () => {
    const handleClick = jest.fn();
    render(
      <AccessibleButton onClick={handleClick}>
        Click me
      </AccessibleButton>
    );
    
    screen.getByRole('button').click();
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  test('applies disabled state', () => {
    render(
      <AccessibleButton disabled>
        Disabled Button
      </AccessibleButton>
    );
    
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });
});

describe('AccessibleLinkButton', () => {
  test('renders link with href', () => {
    render(
      <AccessibleLinkButton href="/test">
        Go to test
      </AccessibleLinkButton>
    );
    
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/test');
  });

  test('applies external link attributes', () => {
    render(
      <AccessibleLinkButton href="https://example.com" external>
        External Link
      </AccessibleLinkButton>
    );
    
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  test('applies variant classes', () => {
    render(
      <AccessibleLinkButton href="/test" variant="success">
        Success Link
      </AccessibleLinkButton>
    );
    
    const link = screen.getByRole('link');
    expect(link).toHaveClass('bg-green-600');
  });
});

describe('AccessibleIconButton', () => {
  test('renders icon button with aria-label', () => {
    render(
      <AccessibleIconButton aria-label="Close dialog">
        ×
      </AccessibleIconButton>
    );
    
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-label', 'Close dialog');
  });

  test('applies size classes', () => {
    render(
      <AccessibleIconButton aria-label="Close" size="lg">
        ×
      </AccessibleIconButton>
    );
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('h-12', 'w-12');
  });

  test('applies variant classes', () => {
    render(
      <AccessibleIconButton aria-label="Close" variant="ghost">
        ×
      </AccessibleIconButton>
    );
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('hover:bg-accent');
  });

  test('handles click events', () => {
    const handleClick = jest.fn();
    render(
      <AccessibleIconButton aria-label="Close" onClick={handleClick}>
        ×
      </AccessibleIconButton>
    );
    
    screen.getByRole('button').click();
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
}); 