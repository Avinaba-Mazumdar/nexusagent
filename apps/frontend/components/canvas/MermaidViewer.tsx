'use client';

import * as React from 'react';
import DOMPurify from 'dompurify';
import { Check, Code, Copy, Eye, Maximize2, Minimize2, RefreshCw, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// Mermaid renders node labels as HTML inside <foreignObject>, so allow the SVG and HTML profiles.
const sanitizeSvg = (svg: string): string =>
    DOMPurify.sanitize(svg, {
        USE_PROFILES: { svg: true, svgFilters: true, html: true },
        ADD_TAGS: ['foreignObject'],
        HTML_INTEGRATION_POINTS: { foreignobject: true },
    });

// Mermaid (~1 MB) is loaded on first diagram only, keeping it out of the main bundle.
// Its config is global, so initialize + render run one at a time to stop themes racing.
let renderQueue: Promise<unknown> = Promise.resolve();

function renderMermaidSerialized(id: string, chart: string, isDark: boolean): Promise<string> {
    const job = renderQueue.then(async () => {
        const { default: mermaid } = await import('mermaid');
        mermaid.initialize({
            startOnLoad: false,
            suppressErrorRendering: true,
            theme: isDark ? 'dark' : 'neutral',
            securityLevel: 'strict',
            fontFamily: 'JetBrains Mono, monospace, sans-serif'
        });
        const { svg } = await mermaid.render(id, chart);
        return svg;
    });
    renderQueue = job.catch(() => undefined);
    return job;
}

const PAN_STEP_PX = 40;

export interface MermaidViewerProps {
    chart: string;
    isDark?: boolean;
    title?: string;
    className?: string;
}

export function MermaidViewer({ chart, isDark = false, title = 'Architecture Sequence / Topology Diagram', className = '' }: MermaidViewerProps) {
    const [svgContent, setSvgContent] = React.useState<string>('');
    const [renderError, setRenderError] = React.useState<string | null>(null);
    const [isLoading, setIsLoading] = React.useState(true);
    const [zoom, setZoom] = React.useState(1.0);
    const [isPanActive, setIsPanActive] = React.useState(false);
    const [panOffset, setPanOffset] = React.useState({ x: 0, y: 0 });
    const [dragStart, setDragStart] = React.useState<{ x: number; y: number } | null>(null);
    const [showSource, setShowSource] = React.useState(false);
    const [copied, setCopied] = React.useState(false);
    const [isExpanded, setIsExpanded] = React.useState(false);

    const containerRef = React.useRef<HTMLDivElement>(null);
    const renderIdRef = React.useRef<string>(`mermaid-${Math.random().toString(36).substring(2, 9)}`);

    // Clean chart content (strip accidental markdown fences if passed with backticks and auto-quote labels with pipes)
    const cleanChart = React.useMemo(() => {
        let code = chart.trim();
        if (code.startsWith('```mermaid')) {
            code = code.replace(/^```mermaid\s*/i, '').replace(/```$/, '');
        } else if (code.startsWith('```')) {
            code = code.replace(/^```\s*/, '').replace(/```$/, '');
        }
        // Auto-fix unquoted node labels with pipes, e.g. Node[Label | Detail] -> Node["Label | Detail"]
        code = code.replace(/(\w+)\[([^"\]\r\n]*\|[^"\]\r\n]*)\]/g, '$1["$2"]');
        return code.trim();
    }, [chart]);

    React.useEffect(() => {
        let isMounted = true;
        setIsLoading(true);
        setRenderError(null);

        const renderDiagram = async () => {
            if (!cleanChart) {
                if (isMounted) setIsLoading(false);
                return;
            }

            const uniqueId = `${renderIdRef.current}-${Date.now()}`;
            try {
                const svg = await renderMermaidSerialized(uniqueId, cleanChart, isDark);
                if (isMounted) {
                    setSvgContent(sanitizeSvg(svg));
                    setRenderError(null);
                    setIsLoading(false);
                }
            } catch (err: unknown) {
                // Remove any leaked error container Mermaid 11.x might have attached to body
                try {
                    const stray = document.getElementById(`d${uniqueId}`) || document.getElementById(uniqueId);
                    if (stray) stray.remove();
                    document.querySelectorAll('svg[id^="mermaid-"]').forEach((el) => {
                        if (el.parentElement === document.body) el.remove();
                    });
                } catch {
                    // Ignore DOM cleanup error
                }

                if (isMounted) {
                    const message = err instanceof Error ? err.message : 'Invalid Mermaid diagram syntax';
                    setRenderError(message);
                    setIsLoading(false);
                }
            }
        };

        const timeout = setTimeout(renderDiagram, 50);
        return () => {
            isMounted = false;
            clearTimeout(timeout);
        };
    }, [cleanChart, isDark]);

    const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.15, 2.5));
    const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.15, 0.4));
    const handleReset = () => {
        setZoom(1.0);
        setPanOffset({ x: 0, y: 0 });
    };

    // Pointer events cover mouse, pen and touch with one code path.
    const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
        if (e.pointerType === 'mouse' && e.button !== 0) return; // Primary click only
        e.currentTarget.setPointerCapture?.(e.pointerId);
        setIsPanActive(true);
        setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
    };

    const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
        if (!isPanActive || !dragStart) return;
        setPanOffset({
            x: e.clientX - dragStart.x,
            y: e.clientY - dragStart.y
        });
    };

    const handlePointerUp = () => {
        setIsPanActive(false);
        setDragStart(null);
    };

    const handleViewportKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
        const pan = (dx: number, dy: number) => setPanOffset((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
        const actions: Record<string, () => void> = {
            ArrowLeft: () => pan(PAN_STEP_PX, 0),
            ArrowRight: () => pan(-PAN_STEP_PX, 0),
            ArrowUp: () => pan(0, PAN_STEP_PX),
            ArrowDown: () => pan(0, -PAN_STEP_PX),
            '+': handleZoomIn,
            '=': handleZoomIn,
            '-': handleZoomOut,
            '0': handleReset
        };
        const action = actions[e.key];
        if (action) {
            e.preventDefault();
            action();
        }
    };

    // Maximized view behaves as a modal: Escape closes it and Tab stays inside.
    const rootRef = React.useRef<HTMLDivElement>(null);
    React.useEffect(() => {
        if (!isExpanded) return;
        const previouslyFocused = document.activeElement as HTMLElement | null;
        rootRef.current?.focus();
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                setIsExpanded(false);
                return;
            }
            if (e.key !== 'Tab' || !rootRef.current) return;
            const focusable = rootRef.current.querySelectorAll<HTMLElement>('button, [tabindex="0"]');
            if (focusable.length === 0) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        };
        document.addEventListener('keydown', onKeyDown);
        return () => {
            document.removeEventListener('keydown', onKeyDown);
            previouslyFocused?.focus?.();
        };
    }, [isExpanded]);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(cleanChart);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Clipboard access blocked
        }
    };

    const isZoomedOrExpanded = isExpanded || zoom !== 1;

    return (
        <>
            {isExpanded && (
                <div className="fixed inset-0 z-40 bg-black/60" onClick={() => setIsExpanded(false)} aria-hidden="true" data-testid="mermaid-backdrop" />
            )}
            <div
                ref={rootRef}
                tabIndex={-1}
                role={isExpanded ? 'dialog' : undefined}
                aria-modal={isExpanded ? true : undefined}
                aria-label={isExpanded ? title : undefined}
                className={`my-3 rounded-2xl border border-border bg-card shadow-xs overflow-hidden transition-all duration-200 focus:outline-none ${
                    isExpanded ? 'fixed inset-4 z-50 shadow-2xl flex flex-col' : ''
                } ${className}`}
            >
                {/* Diagram Toolbar */}
                <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-secondary/30 gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                        <Badge variant="soft" className="text-[10px] font-mono font-bold tracking-tight">
                            Mermaid.js SVG
                        </Badge>
                        <span className="text-xs font-heading font-semibold text-foreground truncate">{title}</span>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                        <span className="text-[10px] font-mono text-muted-foreground mr-1 hidden sm:inline">{(zoom * 100).toFixed(0)}%</span>

                        {/* Pan/Zoom Controls */}
                        <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            onClick={handleZoomIn}
                            aria-label="Zoom diagram in"
                            className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                        >
                            <ZoomIn className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            onClick={handleZoomOut}
                            aria-label="Zoom diagram out"
                            className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                        >
                            <ZoomOut className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            onClick={handleReset}
                            aria-label="Reset zoom and position"
                            className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                        >
                            <RotateCcw className="h-3.5 w-3.5" />
                        </Button>

                        <div className="h-4 w-[1px] bg-border mx-0.5" />

                        {/* Toggle Code / Diagram View */}
                        <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            onClick={() => setShowSource((prev) => !prev)}
                            aria-label={showSource ? 'View rendered diagram' : 'View diagram source'}
                            className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                        >
                            {showSource ? <Eye className="h-3.5 w-3.5" /> : <Code className="h-3.5 w-3.5" />}
                        </Button>

                        {/* Copy Source */}
                        <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            onClick={handleCopy}
                            aria-label="Copy diagram source"
                            className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                        >
                            {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                        </Button>

                        {/* Maximize / Minimize View */}
                        <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            onClick={() => setIsExpanded((prev) => !prev)}
                            aria-label={isExpanded ? 'Minimize diagram view' : 'Maximize diagram view'}
                            className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                        >
                            {isExpanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
                        </Button>
                    </div>
                </div>

                {/* Diagram Viewport */}
                <div
                    ref={containerRef}
                    tabIndex={0}
                    role="group"
                    aria-label="Diagram viewport. Drag or use arrow keys to pan, plus and minus to zoom, 0 to reset."
                    onPointerDown={handlePointerDown}
                    onPointerMove={handlePointerMove}
                    onPointerUp={handlePointerUp}
                    onPointerCancel={handlePointerUp}
                    onKeyDown={handleViewportKeyDown}
                    className={`relative overflow-hidden flex items-center justify-center p-4 bg-card cursor-grab active:cursor-grabbing select-none ${
                        isZoomedOrExpanded ? 'touch-none' : 'touch-pan-y'
                    } ${isExpanded ? 'flex-1 min-h-[300px]' : 'min-h-[220px] max-h-[480px]'}`}
                >
                    {isLoading && (
                        <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground py-8">
                            <RefreshCw className="h-5 w-5 animate-spin text-primary" />
                            <span className="text-xs font-medium font-mono">Rendering dynamic architecture SVG...</span>
                        </div>
                    )}

                    {!isLoading && renderError && !showSource && (
                        <div className="p-4 text-center space-y-2 max-w-md">
                            <p className="text-xs text-warning font-semibold font-mono">Diagram parsing in progress or syntax error:</p>
                            <p className="text-[11px] text-muted-foreground truncate">{renderError}</p>
                            <Button size="sm" variant="outline" onClick={() => setShowSource(true)} className="text-xs rounded-xl h-7">
                                View Raw Syntax
                            </Button>
                        </div>
                    )}

                    {!isLoading && showSource && (
                        <pre className="w-full h-full p-4 overflow-auto font-mono text-xs bg-secondary/30 text-foreground rounded-xl border border-border">
                            <code>{cleanChart}</code>
                        </pre>
                    )}

                    {!isLoading && !renderError && !showSource && svgContent && (
                        <div
                            style={{
                                transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom})`,
                                transformOrigin: 'center center',
                                transition: isPanActive ? 'none' : 'transform 0.15s ease-out'
                            }}
                            className="w-full flex justify-center [&_svg]:max-w-full [&_svg]:h-auto [&_svg_foreignObject]:overflow-visible transition-transform"
                            dangerouslySetInnerHTML={{ __html: svgContent }}
                        />
                    )}
                </div>

                {/* Footer status pill */}
                <div className="px-3 py-1.5 border-t border-border bg-secondary/15 flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                    <span>Drag or arrow keys to pan • +/- to zoom</span>
                    {isExpanded && <span>Esc to close</span>}
                </div>
            </div>
        </>
    );
}
