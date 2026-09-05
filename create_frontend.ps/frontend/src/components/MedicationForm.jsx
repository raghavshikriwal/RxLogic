import { useId, useState } from 'react';
import { createPlan, createPlanFromText } from '../api.js';

const TIMING_OPTIONS = [
  { value: 'no_preference', label: 'No preference' },
  { value: 'morning', label: 'Morning' },
  { value: 'afternoon', label: 'Afternoon' },
  { value: 'evening', label: 'Evening' },
  { value: 'night', label: 'Night' },
];

const EMPTY_MEDICATION = () => ({
  key: crypto.randomUUID(),
  name: '',
  dosage_mg: '',
  frequency_per_day: 1,
  timing_preference: 'no_preference',
  with_food: '',
});

/** Strips the form's string-typed fields down to the JSON shape /api/plan expects. */
function toPayload(medications) {
  return medications
    .filter((m) => m.name.trim().length > 0)
    .map((m) => ({
      name: m.name.trim(),
      dosage_mg: m.dosage_mg === '' ? null : Number(m.dosage_mg),
      frequency_per_day: Number(m.frequency_per_day) || 1,
      timing_preference: m.timing_preference,
      with_food: m.with_food === '' ? null : m.with_food === 'true',
    }));
}

/**
 * @param {(plan: object) => void} onPlanReady - called with the DailyPlan
 *   response so the parent can render ScheduleTimeline / WarningsPanel.
 * @param {(error: import('../api.js').ApiError) => void} onError
 */
export default function MedicationForm({ onPlanReady, onError }) {
  const [mode, setMode] = useState('structured');
  const [medications, setMedications] = useState([EMPTY_MEDICATION()]);
  const [freeText, setFreeText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const headingId = useId();

  function updateMedication(key, field, value) {
    setMedications((rows) => rows.map((row) => (row.key === key ? { ...row, [field]: value } : row)));
  }

  function addMedication() {
    setMedications((rows) => [...rows, EMPTY_MEDICATION()]);
  }

  function removeMedication(key) {
    setMedications((rows) => (rows.length > 1 ? rows.filter((row) => row.key !== key) : rows));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    onError(null);

    try {
      const plan =
        mode === 'structured'
          ? await createPlan(toPayload(medications))
          : await createPlanFromText(freeText.trim());
      onPlanReady(plan);
    } catch (err) {
      onError(err);
    } finally {
      setIsSubmitting(false);
    }
  }

  const canSubmit =
    mode === 'structured'
      ? medications.some((m) => m.name.trim().length > 0)
      : freeText.trim().length > 0;

  return (
    <section id="build-a-plan" className="border-b border-fog bg-paper py-80">
      <div className="mx-auto max-w-page px-24">
        <div className="flex flex-wrap items-end justify-between gap-24">
          <h2 id={headingId} className="font-clarkson text-heading-sm text-obsidian">
            Build a plan
          </h2>

          <div role="tablist" aria-label="Input mode" className="flex gap-8 rounded-full bg-fog p-8">
            {[
              { value: 'structured', label: 'Add medications' },
              { value: 'free_text', label: 'Describe in words' },
            ].map((tab) => (
              <button
                key={tab.value}
                type="button"
                role="tab"
                aria-selected={mode === tab.value}
                onClick={() => setMode(tab.value)}
                className={[
                  'rounded-full px-16 py-8 font-clarkson text-body-sm font-medium transition-colors duration-200 ease-editorial',
                  mode === tab.value ? 'bg-obsidian text-paper' : 'text-ash hover:text-obsidian',
                ].join(' ')}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} aria-labelledby={headingId} className="mt-40">
          {mode === 'structured' ? (
            <div className="flex flex-col gap-16">
              {medications.map((med, index) => (
                <MedicationRow
                  key={med.key}
                  medication={med}
                  index={index}
                  canRemove={medications.length > 1}
                  onChange={(field, value) => updateMedication(med.key, field, value)}
                  onRemove={() => removeMedication(med.key)}
                />
              ))}

              <button
                type="button"
                onClick={addMedication}
                className="self-start rounded-full border border-fog px-16 py-8 font-clarkson text-body-sm text-obsidian transition-colors duration-200 ease-editorial hover:border-obsidian"
              >
                + Add another medication
              </button>
            </div>
          ) : (
            <label className="block">
              <span className="mb-8 block font-clarkson text-body-sm text-ash">
                List your medications the way you'd say them out loud — dosage and timing included if you know them.
              </span>
              <textarea
                value={freeText}
                onChange={(e) => setFreeText(e.target.value)}
                rows={4}
                placeholder="Metformin 500mg twice a day, and 10mg atorvastatin at night."
                className="w-full rounded-lg border border-fog bg-paper px-16 py-16 font-clarkson text-base text-obsidian placeholder:text-slate focus:border-obsidian"
              />
            </label>
          )}

          <button
            type="submit"
            disabled={!canSubmit || isSubmitting}
            className="mt-32 rounded-none bg-charcoal px-32 py-16 font-clarkson text-body-sm text-paper transition-colors duration-200 ease-editorial hover:bg-obsidian disabled:cursor-not-allowed disabled:bg-fog disabled:text-slate"
          >
            {isSubmitting ? 'Generating plan…' : 'Generate plan'}
          </button>
        </form>
      </div>
    </section>
  );
}

function MedicationRow({ medication, index, canRemove, onChange, onRemove }) {
  const rowId = useId();

  return (
    <fieldset className="grid grid-cols-1 gap-16 rounded-lg border border-fog p-24 sm:grid-cols-[2fr_1fr_1fr_1fr_auto]">
      <legend className="sr-only">Medication {index + 1}</legend>

      <label className="block">
        <span className="mb-8 block font-clarkson text-caption text-slate">Name</span>
        <input
          type="text"
          required
          value={medication.name}
          onChange={(e) => onChange('name', e.target.value)}
          placeholder="e.g. Metformin"
          id={`${rowId}-name`}
          className="w-full rounded-lg border border-fog px-16 py-8 font-clarkson text-base text-obsidian placeholder:text-slate focus:border-obsidian"
        />
      </label>

      <label className="block">
        <span className="mb-8 block font-clarkson text-caption text-slate">Dosage (mg)</span>
        <input
          type="number"
          min="0"
          step="any"
          value={medication.dosage_mg}
          onChange={(e) => onChange('dosage_mg', e.target.value)}
          className="w-full rounded-lg border border-fog px-16 py-8 font-clarkson text-base text-obsidian focus:border-obsidian"
        />
      </label>

      <label className="block">
        <span className="mb-8 block font-clarkson text-caption text-slate">Times per day</span>
        <input
          type="number"
          min="1"
          max="6"
          value={medication.frequency_per_day}
          onChange={(e) => onChange('frequency_per_day', e.target.value)}
          className="w-full rounded-lg border border-fog px-16 py-8 font-clarkson text-base text-obsidian focus:border-obsidian"
        />
      </label>

      <label className="block">
        <span className="mb-8 block font-clarkson text-caption text-slate">Preferred timing</span>
        <select
          value={medication.timing_preference}
          onChange={(e) => onChange('timing_preference', e.target.value)}
          className="w-full rounded-lg border border-fog bg-paper px-16 py-8 font-clarkson text-base text-obsidian focus:border-obsidian"
        >
          {TIMING_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <div className="flex items-end justify-start sm:justify-center">
        <button
          type="button"
          onClick={onRemove}
          disabled={!canRemove}
          aria-label={`Remove medication ${index + 1}`}
          className="rounded-full border border-fog px-16 py-8 font-clarkson text-caption text-ash transition-colors duration-200 ease-editorial hover:border-obsidian hover:text-obsidian disabled:cursor-not-allowed disabled:opacity-40"
        >
          Remove
        </button>
      </div>
    </fieldset>
  );
}