import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vite-plus/test';
import { Badge } from './badge';

describe('Badge component', () => {
    it('renders as a span element to preserve hydration invariants', () => {
        render(<Badge>Test Badge</Badge>);
        const badge = screen.getByText('Test Badge');
        expect(badge).toBeInTheDocument();
        expect(badge.tagName.toLowerCase()).toBe('span');
    });

    it('applies variant classes correctly', () => {
        const { rerender } = render(<Badge variant="soft">Soft Badge</Badge>);
        const badge = screen.getByText('Soft Badge');
        expect(badge).toHaveClass('bg-accent');
        expect(badge).toHaveClass('text-accent-foreground');

        rerender(<Badge variant="outline">Outline Badge</Badge>);
        const outlineBadge = screen.getByText('Outline Badge');
        expect(outlineBadge).toHaveClass('border-border');
        expect(outlineBadge).toHaveClass('bg-card');
    });
});
