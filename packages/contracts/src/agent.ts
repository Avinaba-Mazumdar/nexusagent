export interface PlanStep {
    stepNumber: number;
    description: string;
    status: 'pending' | 'in_progress' | 'completed' | 'failed';
    tool?: string | null;
}

/** A source shown to the model. The answer cites it inline as `[label]`, e.g. `[S1]`. */
export interface Citation {
    id: string;
    label: string;
    chunkId: string;
    documentId: string;
    filename: string;
    startLine?: number | null;
    endLine?: number | null;
    headerPath: string[];
    preview: string;
}

export type Grounding = 'grounded' | 'weak' | 'none';

/** Retrieved text that looks like instructions (kept inside untrusted delimiters, but reported). */
export interface InjectionWarning {
    filename: string;
    reason: string;
}

/** Payload of the final `done` SSE event. */
export interface AgentInvokeResponse {
    sessionId: string;
    /** Set when the turn was saved to chat history (Google users only). */
    conversationId?: string | null;
    query: string;
    response: string;
    nodeHistory: string[];
    plan: PlanStep[];
    citations: Citation[];
    injectionWarnings: InjectionWarning[];
    mermaidDiagrams: string[];
    grounding: Grounding;
    isComplete: boolean;
    completedAt?: string | null;
}
