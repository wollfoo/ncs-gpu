import { describe, it, expect } from 'vitest';
import { buildJob } from './index';

describe('buildJob', () => {
  it('wraps payload into job spec', () => {
    const job = buildJob('demo', { value: 42 });
    expect(job.id).toBe('demo');
    expect(job.payload).toEqual({ value: 42 });
  });
});
