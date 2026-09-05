import { useRef, useState } from 'react';
import Hero from '../components/Hero.jsx';
import MedicationForm from '../components/MedicationForm.jsx';
import ErrorBanner from '../components/ErrorBanner.jsx';
import PlanResult from '../components/PlanResult.jsx';

export default function HomePage() {
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState(null);
  const resultRef = useRef(null);

  function handlePlanReady(nextPlan) {
    setPlan(nextPlan);
    // Scroll the new result into view — the form can sit well above the
    // fold once a couple of medication rows are added.
    requestAnimationFrame(() => {
      resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  return (
    <>
      <Hero />
      <MedicationForm onPlanReady={handlePlanReady} onError={setError} />

      {error && (
        <div className="bg-paper px-24 pt-40">
          <div className="mx-auto max-w-page">
            <ErrorBanner error={error} />
          </div>
        </div>
      )}

      {plan && (
        <div ref={resultRef}>
          <PlanResult plan={plan} />
        </div>
      )}
    </>
  );
}