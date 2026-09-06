/**
 * Thin fetch wrapper around the RxLogic API.
 *
 * Kept dependency-free (no axios) on purpose — four endpoints don't
 * justify a client library. Every function throws an `ApiError` on
 * failure so callers get the backend's actual error code + message
 * (routes/api.py's @api.errorhandler set) instead of a generic
 * "request failed".
 */

const BASE_URL = import.meta.env.VITE_API_BASE ?? '';

/** Mirrors the `error` field routes/api.py sends for each RxLogicError subclass. */
export const ApiErrorCode = Object.freeze({
  SCHEMA_VALIDATION: 'schema_validation_error',
  UNKNOWN_MEDICATION: 'unknown_medication',
  INSUFFICIENT_DATA: 'insufficient_data',
  NO_FEASIBLE_SCHEDULE: 'no_feasible_schedule',
  EXTERNAL_API_ERROR: 'external_api_error',
  LLM_API_ERROR: 'llm_api_error',
  REASONING_ERROR: 'reasoning_error',
  NETWORK: 'network_error',
});

export class ApiError extends Error {
  /**
   * @param {string} message - human-readable message from the backend
   * @param {string} code - one of ApiErrorCode
   * @param {number|null} status - HTTP status code, null for network failures
   */
  constructor(message, code, status = null) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
  } catch {
    throw new ApiError(
      'Could not reach RxLogic. Check your connection and try again.',
      ApiErrorCode.NETWORK,
    );
  }

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const body = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    throw new ApiError(
      body?.message ?? `Request failed with status ${response.status}.`,
      body?.error ?? ApiErrorCode.REASONING_ERROR,
      response.status,
    );
  }

  return body;
}

/**
 * POST /api/plan — structured medication list -> DailyPlan.
 * @param {Array<{name: string, dosage_mg?: number, frequency_per_day?: number, timing_preference?: string, with_food?: boolean}>} medications
 */
export function createPlan(medications) {
  return request('/api/plan', {
    method: 'POST',
    body: JSON.stringify({ medications }),
  });
}

/**
 * POST /api/plan/nl — free-text description -> DailyPlan.
 * @param {string} text
 */
export function createPlanFromText(text) {
  return request('/api/plan/nl', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

/**
 * GET /api/plans — most recent logged plans, newest first.
 * @param {number} limit
 */
export function listPlans(limit = 20) {
  return request(`/api/plans?limit=${limit}`, { method: 'GET' });
}

/** GET /api/health */
export function checkHealth() {
  return request('/api/health', { method: 'GET' });
}