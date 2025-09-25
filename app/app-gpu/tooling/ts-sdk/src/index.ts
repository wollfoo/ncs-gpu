export interface JobSpec {
  id: string;
  payload: Record<string, unknown>;
}

export function buildJob(id: string, payload: Record<string, unknown>): JobSpec {
  return { id, payload };
}
