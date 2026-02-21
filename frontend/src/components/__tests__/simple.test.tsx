import React from 'react';
import { render, screen } from '@testing-library/react';

describe('Simple Test', () => {
  test('renders a simple component', () => {
    render(<div data-testid="test-element">Hello World</div>);
    expect(screen.getByTestId('test-element')).toBeInTheDocument();
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  test('basic math works', () => {
    expect(2 + 2).toBe(4);
  });
}); 