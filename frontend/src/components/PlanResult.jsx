import ScheduleTimeline from './ScheduleTimeline.jsx';
import WarningsPanel from './WarningsPanel.jsx';
import GoalTrace from './GoalTrace.jsx';
import CoverageSummary from './CoverageSummary.jsx';
import NameCorrections from './NameCorrections.jsx';
import FoodGuidance from './FoodGuidance.jsx';

/**
 * @param {{entries: object[], warnings: object[], goal_trace: string[], coverage?: object | null, name_resolutions?: object[], food_guidance?: object[]}} plan
 *   - the serialized DailyPlan from /api/plan or /api/plan/nl.
 */
export default function PlanResult({ plan }) {
  return (
    <section aria-labelledby="plan-result-heading" className="bg-paper py-80">
      <div className="mx-auto grid max-w-page grid-cols-1 gap-56 px-24 lg:grid-cols-[3fr_2fr]">
        <div>
          <h2 id="plan-result-heading" className="font-clarkson text-heading-sm text-obsidian">
            Today's schedule
          </h2>
          <div className="mt-40">
            <ScheduleTimeline entries={plan.entries} />
          </div>
          <div className="mt-40">
            <GoalTrace trace={plan.goal_trace} />
          </div>
        </div>

        <div>
          <h2 className="font-clarkson text-heading-sm text-obsidian">Interaction check</h2>
          <div className="mt-40 flex flex-col gap-24">
            <NameCorrections resolutions={plan.name_resolutions} />
            <CoverageSummary coverage={plan.coverage} />
            <WarningsPanel warnings={plan.warnings} />
            <FoodGuidance guidance={plan.food_guidance} />
          </div>
        </div>
      </div>
    </section>
  );
}