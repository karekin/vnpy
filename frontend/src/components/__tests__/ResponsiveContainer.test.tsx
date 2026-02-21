import React from 'react';
import { render, screen } from '@testing-library/react';
import { ResponsiveContainer, ResponsiveGrid, ResponsiveTable, ResponsiveCard } from '../ui/ResponsiveContainer';

describe('ResponsiveContainer', () => {
  test('renders children with default props', () => {
    render(
      <ResponsiveContainer>
        <div data-testid="test-content">Test Content</div>
      </ResponsiveContainer>
    );
    
    expect(screen.getByTestId('test-content')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    render(
      <ResponsiveContainer className="custom-class">
        <div data-testid="test-content">Test Content</div>
      </ResponsiveContainer>
    );
    
    const container = screen.getByTestId('test-content').parentElement;
    expect(container).toHaveClass('custom-class');
  });

  test('applies responsive classes', () => {
    render(
      <ResponsiveContainer 
        mobile="w-full" 
        tablet="md:w-3/4" 
        desktop="lg:w-2/3"
      >
        <div data-testid="test-content">Test Content</div>
      </ResponsiveContainer>
    );
    
    const container = screen.getByTestId('test-content').parentElement;
    expect(container).toHaveClass('w-full', 'md:w-3/4', 'lg:w-2/3');
  });
});

describe('ResponsiveGrid', () => {
  test('renders grid with default props', () => {
    render(
      <ResponsiveGrid>
        <div data-testid="grid-item">Grid Item</div>
      </ResponsiveGrid>
    );
    
    const grid = screen.getByTestId('grid-item').parentElement;
    expect(grid).toHaveClass('grid');
  });

  test('applies custom grid columns', () => {
    render(
      <ResponsiveGrid cols={{ mobile: 1, tablet: 2, desktop: 3 }}>
        <div data-testid="grid-item">Grid Item</div>
      </ResponsiveGrid>
    );
    
    const grid = screen.getByTestId('grid-item').parentElement;
    expect(grid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3');
  });

  test('applies custom gap', () => {
    render(
      <ResponsiveGrid gap="lg">
        <div data-testid="grid-item">Grid Item</div>
      </ResponsiveGrid>
    );
    
    const grid = screen.getByTestId('grid-item').parentElement;
    expect(grid).toHaveClass('gap-6');
  });
});

describe('ResponsiveTable', () => {
  test('renders table wrapper', () => {
    render(
      <ResponsiveTable>
        <tbody>
          <tr>
            <td data-testid="table-cell">Table Cell</td>
          </tr>
        </tbody>
      </ResponsiveTable>
    );
    
    expect(screen.getByTestId('table-cell')).toBeInTheDocument();
  });

  test('applies striped styling', () => {
    render(
      <ResponsiveTable striped>
        <tbody>
          <tr>
            <td data-testid="table-cell">Table Cell</td>
          </tr>
        </tbody>
      </ResponsiveTable>
    );
    
    const table = screen.getByTestId('table-cell').closest('table');
    expect(table).toHaveClass('divide-y', 'divide-gray-200');
  });

  test('applies hover styling', () => {
    render(
      <ResponsiveTable hover>
        <tbody>
          <tr>
            <td data-testid="table-cell">Table Cell</td>
          </tr>
        </tbody>
      </ResponsiveTable>
    );
    
    const table = screen.getByTestId('table-cell').closest('table');
    expect(table).toHaveClass('hover:bg-gray-50');
  });
});

describe('ResponsiveCard', () => {
  test('renders card with title', () => {
    render(
      <ResponsiveCard title="Test Card">
        <div data-testid="card-content">Card Content</div>
      </ResponsiveCard>
    );
    
    expect(screen.getByText('Test Card')).toBeInTheDocument();
    expect(screen.getByTestId('card-content')).toBeInTheDocument();
  });

  test('renders card with subtitle', () => {
    render(
      <ResponsiveCard title="Test Card" subtitle="Test Subtitle">
        <div data-testid="card-content">Card Content</div>
      </ResponsiveCard>
    );
    
    expect(screen.getByText('Test Card')).toBeInTheDocument();
    expect(screen.getByText('Test Subtitle')).toBeInTheDocument();
  });

  test('applies custom shadow', () => {
    render(
      <ResponsiveCard shadow="lg">
        <div data-testid="card-content">Card Content</div>
      </ResponsiveCard>
    );
    
    // Find the element that contains the shadow-lg class
    const elements = document.querySelectorAll('*');
    const elementWithShadow = Array.from(elements).find(el => 
      el.classList.contains('shadow-lg')
    );
    
    expect(elementWithShadow).toBeTruthy();
    expect(elementWithShadow).toHaveClass('shadow-lg');
  });

  test('applies custom padding', () => {
    render(
      <ResponsiveCard padding="lg">
        <div data-testid="card-content">Card Content</div>
      </ResponsiveCard>
    );
    
    const content = screen.getByTestId('card-content').parentElement;
    expect(content).toHaveClass('p-6');
  });
}); 