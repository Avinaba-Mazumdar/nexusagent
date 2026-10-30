import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vite-plus/test';
import { Button } from './button';

describe('Button component', () => {
    it('renders with default props and text content', () => {
        render(<Button>Click me</Button>);
        const button = screen.getByRole('button', { name: /click me/i });
        expect(button).toBeInTheDocument();
        expect(button).not.toBeDisabled();
    });

    it('handles click events', async () => {
        const user = userEvent.setup();
        const handleClick = vi.fn();
        render(<Button onClick={handleClick}>Trigger Action</Button>);

        const button = screen.getByRole('button', { name: /trigger action/i });
        await user.click(button);
        expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('respects the disabled attribute', async () => {
        const user = userEvent.setup();
        const handleClick = vi.fn();
        render(
            <Button disabled onClick={handleClick}>
                Disabled Button
            </Button>
        );

        const button = screen.getByRole('button', { name: /disabled button/i });
        expect(button).toBeDisabled();
        await user.click(button);
        expect(handleClick).not.toHaveBeenCalled();
    });

    it('renders different variants appropriately', () => {
        const { rerender } = render(<Button variant="outline">Outline</Button>);
        expect(screen.getByRole('button')).toHaveClass('border');

        rerender(<Button variant="destructive">Destructive</Button>);
        expect(screen.getByRole('button')).toBeInTheDocument();
    });
});
