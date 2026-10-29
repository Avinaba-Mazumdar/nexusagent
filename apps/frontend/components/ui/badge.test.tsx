import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
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

        rerender(<Badge variant="secondary">RFC-104:L128</Badge>);
        const secondaryBadge = screen.getByText('RFC-104:L128');
        expect(secondaryBadge).toHaveClass('border-border');
        expect(secondaryBadge).toHaveClass('bg-secondary');
        expect(secondaryBadge).toHaveClass('text-secondary-foreground');
    });
});
