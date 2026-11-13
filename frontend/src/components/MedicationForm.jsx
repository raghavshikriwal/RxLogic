
import { useId, useState } from 'react';
import { createPlan, createPlanFromText } from '../api.js';

const TIMING_OPTIONS = [
  { value: 'no_preference', label: 'No preference' },
  { value: 'morning', label: 'Morning' },
  { value: 'afternoon', label: 'Afternoon' },
  { value: 'evening', label: 'Evening' },
  { value: 'night', label: 'Night' },
];

const FOOD_OPTIONS = [
  { value: '', label: 'Not specified' },
  { value: 'true', label: 'With food' },
  { value: 'false', label: 'Without food' },
];

function createMedication() {
  return {
    key: crypto.randomUUID(),
    name: '',
    dosage_mg: '',
    frequency_per_day: '1',
    timing_preference: 'no_preference',
    with_food: '',
  };
}

function hasInput(medication) {
  return (
    medication.name.trim() !== '' ||
    medication.dosage_mg !== ''
  );
}

function toPayload(medications) {
  return medications
    .filter((medication) => medication.name.trim() !== '')
    .map((medication) => ({
      name: medication.name.trim(),
      dosage_mg:
        medication.dosage_mg === ''
          ? null
          : Number(medication.dosage_mg),
      frequency_per_day: Number(medication.frequency_per_day),
      timing_preference: medication.timing_preference,
      with_food:
        medication.with_food === ''
          ? null
          : medication.with_food === 'true',
    }));
}

function validateMedications(medications) {
  const errors = {};

  const activeRows = medications.filter(hasInput);

  if (activeRows.length === 0) {
    return {
      form: 'Please enter at least one medication.',
      rows: {},
    };
  }

  activeRows.forEach((medication) => {
    const rowErrors = {};

    const dosage =
      medication.dosage_mg === ''
        ? null
        : Number(medication.dosage_mg);

    const frequency = Number(
      medication.frequency_per_day
    );

    if (!medication.name.trim()) {
      rowErrors.name = 'Medication name is required.';
    }

    if (
      dosage !== null &&
      (!Number.isFinite(dosage) || dosage < 0)
    ) {
      rowErrors.dosage_mg = 'Enter a valid non-negative dosage.';
    }

    if (
      !Number.isInteger(frequency) ||
      frequency < 1 ||
      frequency > 6
    ) {
      rowErrors.frequency_per_day =
        'Enter a whole number between 1 and 6.';
    }

    if (Object.keys(rowErrors).length > 0) {
      errors[medication.key] = rowErrors;
    }
  });

  return {
    form: Object.keys(errors).length
      ? 'Please correct the highlighted fields.'
      : '',
    rows: errors,
  };
}

export default function MedicationForm({
  onPlanReady,
  onError,
}) {
  const [mode, setMode] = useState('structured');

  const [medications, setMedications] = useState([
    createMedication(),
  ]);

  const [freeText, setFreeText] = useState('');
  const [foodContext, setFoodContext] = useState('');
  const [conditionContext, setConditionContext] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [validation, setValidation] = useState({
    form: '',
    rows: {},
  });

  const headingId = useId();

  function updateMedication(key, field, value) {
    setMedications((rows) =>
      rows.map((row) =>
        row.key === key
          ? { ...row, [field]: value }
          : row
      )
    );

    setValidation((current) => ({
      form: '',
      rows: {
        ...current.rows,
        [key]: {
          ...current.rows[key],
          [field]: '',
        },
      },
    }));
  }

  function addMedication() {
    setMedications((rows) => [
      ...rows,
      createMedication(),
    ]);
  }

  function removeMedication(key) {
    setMedications((rows) =>
      rows.length > 1
        ? rows.filter((row) => row.key !== key)
        : rows
    );

    setValidation((current) => {
      const rows = { ...current.rows };
      delete rows[key];

      return {
        ...current,
        rows,
      };
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (isSubmitting) return;

    if (mode === 'structured') {
      const result = validateMedications(medications);

      setValidation(result);

      if (result.form) return;
    } else {
      if (!freeText.trim()) {
        setValidation({
          form: 'Please describe your medication details.',
          rows: {},
        });
        return;
      }

      setValidation({
        form: '',
        rows: {},
      });
    }

    setIsSubmitting(true);
    onError(null);

    try {
      const patientContext = {
        foods: foodContext.split(',').map((value) => value.trim()).filter(Boolean),
        conditions: conditionContext.split(',').map((value) => value.trim()).filter(Boolean),
      };
      const plan =
        mode === 'structured'
          ? await createPlan(toPayload(medications), patientContext)
          : await createPlanFromText(freeText.trim(), patientContext);

      onPlanReady(plan);
    } catch (error) {
      onError(error);
    } finally {
      setIsSubmitting(false);
    }
  }

  const canSubmit =
    mode === 'structured'
      ? medications.some(hasInput)
      : freeText.trim().length > 0;

  return (
    <section
      id="build-a-plan"
      className="border-b border-fog bg-paper py-80"
    >
      <div className="mx-auto max-w-page px-24">

        {/* Section heading */}

        <div className="flex flex-wrap items-end justify-between gap-24">
          <div>
            <p className="mb-8 font-clarkson text-caption font-semibold uppercase tracking-wider text-teal">
              Medication details
            </p>

            <h2
              id={headingId}
              className="font-clarkson text-heading-sm text-obsidian"
            >
              Build a plan
            </h2>
          </div>

          {/* Input mode selector */}

          <div
            role="tablist"
            aria-label="Medication input method"
            className="flex gap-8 rounded-full bg-fog p-8"
          >
            {[
              {
                value: 'structured',
                label: 'Add medications',
              },
              {
                value: 'free_text',
                label: 'Describe in words',
              },
            ].map((tab) => (
              <button
                key={tab.value}
                type="button"
                role="tab"
                aria-selected={mode === tab.value}
                onClick={() => {
                  setMode(tab.value);

                  setValidation({
                    form: '',
                    rows: {},
                  });
                }}
                className={[
                  'rounded-full px-16 py-8 font-clarkson text-body-sm font-medium transition-colors duration-200 ease-editorial',
                  mode === tab.value
                    ? 'bg-obsidian text-paper'
                    : 'text-ash hover:text-obsidian',
                ].join(' ')}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Form */}

        <form
          onSubmit={handleSubmit}
          aria-labelledby={headingId}
          noValidate
          className="mt-40"
        >
          {mode === 'structured' ? (
            <div className="flex flex-col gap-16">

              {medications.map((medication, index) => (
                <MedicationRow
                  key={medication.key}
                  medication={medication}
                  index={index}
                  canRemove={medications.length > 1}
                  errors={
                    validation.rows[medication.key] || {}
                  }
                  onChange={(field, value) =>
                    updateMedication(
                      medication.key,
                      field,
                      value
                    )
                  }
                  onRemove={() =>
                    removeMedication(medication.key)
                  }
                />
              ))}

              <button
                type="button"
                onClick={addMedication}
                className="self-start rounded-full border border-fog px-16 py-8 font-clarkson text-body-sm text-obsidian transition-colors duration-200 ease-editorial hover:border-teal hover:text-teal"
              >
                + Add another medication
              </button>
            </div>
          ) : (
            <label className="block">
              <span className="mb-8 block font-clarkson text-body-sm text-ash">
                Describe your medication details, including
                names, prescribed dosage and timing if known.
              </span>

              <textarea
                value={freeText}
                onChange={(event) => {
                  setFreeText(event.target.value);

                  setValidation({
                    form: '',
                    rows: {},
                  });
                }}
                rows={5}
                maxLength={4000}
                aria-label="Medication description"
                placeholder="Describe your medication details here..."
                className="w-full rounded-xl border border-fog bg-paper px-16 py-16 font-clarkson text-base text-obsidian placeholder:text-slate focus:border-teal"
              />

              <span className="mt-8 block text-right font-clarkson text-caption text-slate">
                {freeText.length}/4000
              </span>
            </label>
          )}

          <div className="mt-32 grid gap-16 rounded-xl border border-fog p-24 md:grid-cols-2">
            <label className="block">
              <span className="mb-8 block font-clarkson text-body-sm text-obsidian">Relevant foods or supplements (optional)</span>
              <input
                value={foodContext}
                onChange={(event) => setFoodContext(event.target.value)}
                maxLength={500}
                placeholder="e.g. grapefruit, calcium supplement"
                className="w-full rounded-lg border border-fog bg-paper px-16 py-12 font-clarkson text-base text-obsidian placeholder:text-slate focus:border-teal"
              />
              <span className="mt-8 block font-clarkson text-caption text-slate">Separate entries with commas.</span>
            </label>
            <label className="block">
              <span className="mb-8 block font-clarkson text-body-sm text-obsidian">Relevant conditions or populations (optional)</span>
              <input
                value={conditionContext}
                onChange={(event) => setConditionContext(event.target.value)}
                maxLength={500}
                placeholder="e.g. kidney disease, pregnancy"
                className="w-full rounded-lg border border-fog bg-paper px-16 py-12 font-clarkson text-base text-obsidian placeholder:text-slate focus:border-teal"
              />
              <span className="mt-8 block font-clarkson text-caption text-slate">Exact context matching only; this is not a diagnosis.</span>
            </label>
            <p className="font-clarkson text-caption text-slate md:col-span-2">Optional context is used only for this request and is not included in plan-history records. Leave blank if you prefer. Missing context means those checks are not evaluated.</p>
          </div>

          {/* Validation message */}

          {validation.form && (
            <p
              className="mt-16 rounded-lg border border-amber-200 bg-amber-50 px-16 py-12 text-body-sm text-amber-900"
              role="alert"
            >
              {validation.form}
            </p>
          )}

          {/* Submit */}

          <div className="mt-24 flex flex-wrap items-center gap-16">
            <button
              type="submit"
              disabled={!canSubmit || isSubmitting}
              aria-busy={isSubmitting}
              className="btn-primary min-w-44"
            >
              {isSubmitting
                ? 'Generating plan…'
                : 'Generate plan'}
            </button>

            <p className="max-w-xl text-caption text-slate">
              Educational demonstrator only. Review medication
              details with a qualified healthcare professional.
            </p>
          </div>
        </form>
      </div>
    </section>
  );
}

function MedicationRow({
  medication,
  index,
  canRemove,
  errors,
  onChange,
  onRemove,
}) {
  const rowId = useId();

  function fieldClass(hasError) {
    return [
      'w-full rounded-lg border bg-paper px-16 py-10 font-clarkson text-base text-obsidian',
      'placeholder:text-slate focus:border-teal',
      hasError ? 'border-red-500' : 'border-fog',
    ].join(' ');
  }

  function showError(field) {
    if (!errors[field]) return null;

    return (
      <span
        id={`${rowId}-${field}-error`}
        className="mt-4 block text-caption text-red-700"
      >
        {errors[field]}
      </span>
    );
  }

  return (
    <fieldset className="grid grid-cols-1 gap-16 rounded-xl border border-fog bg-white p-16 sm:p-24 lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_auto]">
      <legend className="sr-only">
        Medication {index + 1}
      </legend>

      {/* Name */}

      <label className="block min-w-0">
        <span className="mb-8 block font-clarkson text-caption text-slate">
          Medication name
        </span>

        <input
          type="text"
          value={medication.name}
          onChange={(event) =>
            onChange('name', event.target.value)
          }
          placeholder="e.g. Metformin"
          autoComplete="off"
          aria-invalid={Boolean(errors.name)}
          aria-describedby={
            errors.name
              ? `${rowId}-name-error`
              : undefined
          }
          className={fieldClass(errors.name)}
        />

        {showError('name')}
      </label>

      {/* Dosage */}

      <label className="block min-w-0">
        <span className="mb-8 block font-clarkson text-caption text-slate">
          Dosage (mg)
        </span>

        <input
          type="number"
          min="0"
          step="any"
          inputMode="decimal"
          value={medication.dosage_mg}
          onChange={(event) =>
            onChange('dosage_mg', event.target.value)
          }
          placeholder="Optional"
          aria-invalid={Boolean(errors.dosage_mg)}
          aria-describedby={
            errors.dosage_mg
              ? `${rowId}-dosage_mg-error`
              : undefined
          }
          className={fieldClass(errors.dosage_mg)}
        />

        {showError('dosage_mg')}
      </label>

      {/* Frequency */}

      <label className="block min-w-0">
        <span className="mb-8 block font-clarkson text-caption text-slate">
          Times per day
        </span>

        <input
          type="number"
          min="1"
          max="6"
          step="1"
          inputMode="numeric"
          value={medication.frequency_per_day}
          onChange={(event) =>
            onChange(
              'frequency_per_day',
              event.target.value
            )
          }
          aria-invalid={Boolean(errors.frequency_per_day)}
          aria-describedby={
            errors.frequency_per_day
              ? `${rowId}-frequency_per_day-error`
              : undefined
          }
          className={fieldClass(errors.frequency_per_day)}
        />

        {showError('frequency_per_day')}
      </label>

      {/* Preferred timing */}

      <label className="block min-w-0">
        <span className="mb-8 block font-clarkson text-caption text-slate">
          Preferred timing
        </span>

        <select
          value={medication.timing_preference}
          onChange={(event) =>
            onChange(
              'timing_preference',
              event.target.value
            )
          }
          className={fieldClass(false)}
        >
          {TIMING_OPTIONS.map((option) => (
            <option
              key={option.value}
              value={option.value}
            >
              {option.label}
            </option>
          ))}
        </select>
      </label>

      {/* Food instruction */}

      <label className="block min-w-0">
        <span className="mb-8 block font-clarkson text-caption text-slate">
          Food instruction
        </span>

        <select
          value={medication.with_food}
          onChange={(event) =>
            onChange('with_food', event.target.value)
          }
          className={fieldClass(false)}
        >
          {FOOD_OPTIONS.map((option) => (
            <option
              key={option.value}
              value={option.value}
            >
              {option.label}
            </option>
          ))}
        </select>
      </label>

      {/* Remove */}

      <div className="flex items-end">
        <button
          type="button"
          onClick={onRemove}
          disabled={!canRemove}
          aria-label={`Remove medication ${index + 1}`}
          className="min-h-44 rounded-full border border-fog px-16 py-8 font-clarkson text-caption text-ash transition-colors duration-200 ease-editorial hover:border-red-400 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Remove
        </button>
      </div>
    </fieldset>
  );
}
