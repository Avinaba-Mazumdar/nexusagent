import { describe, expect, it } from 'vite-plus/test';
import { getMachineId } from './machine-id';

describe('getMachineId', () => {
    it('returns a 64 hex-character SHA-256 hash', async () => {
        const id = await getMachineId();
        expect(id).toMatch(/^[0-9a-f]{64}$/);
    });

    it('returns the same hash when called multiple times in the same environment', async () => {
        const id1 = await getMachineId();
        const id2 = await getMachineId();
        expect(id1).toBe(id2);
    });
});
