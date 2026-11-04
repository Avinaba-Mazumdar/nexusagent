import type { AgentDoneEventWire, CitationWire, InjectionWarningWire, PlanStepWire, SseUsageEvent, WebSourceWire } from './generated';

export type PlanStep = PlanStepWire;

/** A source shown to the model. The answer cites it inline as `[label]`, e.g. `[S1]`. */
export type Citation = CitationWire;

export type Grounding = AgentDoneEventWire['grounding'];

/** Retrieved text that looks like instructions (kept inside untrusted delimiters, but reported). */
export type InjectionWarning = InjectionWarningWire;

/** Token usage record for a pipeline step. */
export type UsageEvent = SseUsageEvent;

/** Web source from Google Search grounding. */
export type WebSource = WebSourceWire;

/** Payload of the final `done` SSE event. */
export type AgentInvokeResponse = AgentDoneEventWire;

/** Payloads of the other `/api/agent/stream` SSE events, keyed by event name. */
export type {
    SseErrorEvent,
    SseGroundingEvent,
    SseNodeStartEvent,
    SsePlanEvent,
    SseStartEvent,
    SseTokenEvent,
    SseToolCallEvent,
    SseToolResultEvent,
    SseUsageEvent,
    WebSourceWire
} from './generated';
