/**
 * Browser device/machine fingerprinting for guest quota enforcement.
 * Produces a stable SHA-256 hex digest of client hardware/browser traits.
 */

export async function getMachineId(): Promise<string> {
    try {
        if (typeof window === 'undefined') {
            return '';
        }

        const nav = window.navigator;
        const screen = window.screen;

        let canvasData = '';
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 200;
            canvas.height = 50;
            const ctx = canvas.getContext('2d');
            if (ctx) {
                ctx.textBaseline = 'top';
                ctx.font = '14px Arial';
                ctx.fillStyle = '#0f172a';
                ctx.fillText('NexusAgent ✓ 0123', 10, 15);
                canvasData = canvas.toDataURL();
            }
        } catch {
            // Canvas fingerprinting blocked or unsupported
        }

        const components: string[] = [
            nav.userAgent || '',
            nav.platform || '',
            nav.language || '',
            (nav.languages || []).join(','),
            `${screen.width}x${screen.height}x${screen.colorDepth}`,
            Intl.DateTimeFormat().resolvedOptions().timeZone || '',
            String(nav.hardwareConcurrency || ''),
            String(nav.maxTouchPoints || ''),
            canvasData
        ];

        const raw = components.join('###');
        const encoder = new TextEncoder();
        const data = encoder.encode(raw);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
    } catch {
        return '';
    }
}
