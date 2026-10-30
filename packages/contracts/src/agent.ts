import type { AgentDoneEventWire, CitationWire, InjectionWarningWire, PlanStepWire } from './generated';

export type PlanStep = PlanStepWire;

/** A source shown to the model. The answer cites it inline as `[label]`, e.g. `[S1]`. */
export type Citation = CitationWire;

export type Grounding = AgentDoneEventWire['grounding'];

/** Retrieved text that looks like instructions (kept inside untrusted delimiters, but reported). */
export type InjectionWarning = InjectionWarningWire;

/** Payload of the final `done` SSE event. */
export type AgentInvokeResponse = AgentDoneEventWire;

/** Payloads of the other `/api/agent/stream` SSE events, keyed by event name. */
export type {
    SseErrorEvent,
    SseGroundingEvent,
    SseNodeStartEvent,
    SsePlanEvent,
    SseRedactEvent,
    SseStartEvent,
    SseTokenEvent,
    SseToolResultEvent
} from './generated';
