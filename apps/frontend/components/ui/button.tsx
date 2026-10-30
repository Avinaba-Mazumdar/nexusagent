import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-all duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer active:scale-[0.98]',
    {
        variants: {
            variant: {
                default: 'bg-primary text-primary-foreground shadow-xs hover:bg-primary-hover',
                soft: 'bg-accent text-accent-foreground border border-border hover:bg-accent/80',
                secondary: 'bg-secondary text-secondary-foreground border border-border hover:bg-secondary/80',
                outline: 'border border-border bg-card text-card-foreground shadow-xs hover:bg-secondary',
                ghost: 'hover:bg-secondary text-muted-foreground hover:text-foreground'
            },
            size: {
                default: 'min-h-11 px-4 py-2.5',
                sm: 'min-h-9 px-3.5 py-1.5 text-xs rounded-lg',
                icon: 'min-h-11 min-w-11 rounded-xl',
                'icon-sm': 'min-h-9 min-w-9 rounded-lg'
            }
        },
        defaultVariants: {
            variant: 'default',
            size: 'default'
        }
    }
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
    asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
});
Button.displayName = 'Button';

export { Button, buttonVariants };
