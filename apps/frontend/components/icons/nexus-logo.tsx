import * as React from 'react';

export interface NexusLogoProps extends React.SVGProps<SVGSVGElement> {
    size?: number | string;
}

export function NexusLogo({ size, className = '', ...props }: NexusLogoProps) {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width={size} height={size} fill="none" className={className} {...props}>
            <rect width="512" height="512" rx="116" fill="var(--primary, #004ea1)" />
            <g fill="var(--primary-foreground, #ffffff)">
                <rect x="180" y="84" width="24" height="60" rx="12" />
                <rect x="244" y="84" width="24" height="60" rx="12" />
                <rect x="308" y="84" width="24" height="60" rx="12" />
                <rect x="180" y="368" width="24" height="60" rx="12" />
                <rect x="244" y="368" width="24" height="60" rx="12" />
                <rect x="308" y="368" width="24" height="60" rx="12" />
                <rect x="84" y="180" width="60" height="24" rx="12" />
                <rect x="84" y="244" width="60" height="24" rx="12" />
                <rect x="84" y="308" width="60" height="24" rx="12" />
                <rect x="368" y="180" width="60" height="24" rx="12" />
                <rect x="368" y="244" width="60" height="24" rx="12" />
                <rect x="368" y="308" width="60" height="24" rx="12" />
                <rect x="208" y="208" width="96" height="96" rx="16" />
            </g>
            <rect x="136" y="136" width="240" height="240" rx="32" stroke="var(--primary-foreground, #ffffff)" strokeWidth="28" fill="none" />
        </svg>
    );
}
