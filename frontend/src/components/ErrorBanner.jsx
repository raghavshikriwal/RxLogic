import { ApiErrorCode } from '../api.js';

/**
 * Copy is written per error code rather than showing the raw backend
 * message everywhere — the backend's message is accurate but written
 * for logs, not for someone deciding what to do next.
 */
const COPY = {
  [ApiErrorCode.SCHEMA_VALIDATION]: {
    title: "That input doesn't match what a medication entry needs.",
    hint: 'Check that every row has a name, and try again.',
  },
  [ApiErrorCode.UNKNOWN_MEDICATION]: {
    title: "One of these medications isn't in RxLogic's knowledge base.",
    hint: "Check the spelling, or try the medication's generic name.",
  },
  [ApiErrorCode.INSUFFICIENT_DATA]: {
    title: 'There isn\u2019t enough interaction data to reason about this combination safely.',
    hint: 'Consult a pharmacist or physician for this pairing.',
  },
  [ApiErrorCode.NO_FEASIBLE_SCHEDULE]: {
    title: 'No schedule satisfies every constraint on these medications.',
    hint: 'Try loosening a timing preference and generate again.',
  },
  [ApiErrorCode.EXTERNAL_API_ERROR]: {
    title: 'The drug-data lookup failed.',
    hint: 'This is usually temporary — try again in a moment.',
  },
  [ApiErrorCode.LLM_API_ERROR]: {
    title: "Couldn't reach the AI parser for free-text input.",
    hint: 'Try again in a moment, or use "Add medications" for structured input instead.',
  },
  [ApiErrorCode.NETWORK]: {
    title: 'Could not reach RxLogic.',
    hint: 'Check your connection and try again.',
  },
  [ApiErrorCode.REASONING_ERROR]: {
    title: 'The reasoning engine could not complete this plan.',
    hint: 'Try again, or adjust the medications and retry.',
  },
};

/**
 * @param {import('../api.js').ApiError|null} error
 */
export default function ErrorBanner({ error }) {
  if (!error) return null;

  const copy = COPY[error.code] ?? COPY[ApiErrorCode.REASONING_ERROR];

  return (
    <div role="alert" className="rounded-lg border border-obsidian bg-paper px-24 py-16">
      <p className="font-clarkson text-body-sm font-medium text-obsidian">{copy.title}</p>
      <p className="mt-4 font-clarkson text-body-sm text-ash">{copy.hint}</p>
    </div>
  );
}