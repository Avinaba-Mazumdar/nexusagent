import { describe, expect, it } from 'vite-plus/test';
import { parseSseBlock } from './useAgentStream';

describe('parseSseBlock', () => {
    it('reads the event name and data', () => {
        expect(parseSseBlock('event: token\ndata: {"a":1}')).toEqual({ eventType: 'token', data: '{"a":1}' });
    });

    it('joins multiple data lines with a newline, per the SSE spec', () => {
        expect(parseSseBlock('event: x\ndata: line one\ndata: line two').data).toBe('line one\nline two');
    });

    it('defaults to the "message" event', () => {
        expect(parseSseBlock('data: hi').eventType).toBe('message');
    });
});
