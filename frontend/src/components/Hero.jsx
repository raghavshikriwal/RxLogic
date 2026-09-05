/**
 * The hero's visual is a 24-hour clock face with dose markers, rendered
 * as inline SVG rather than a stock photo — it's the literal shape of
 * a DailyPlan, which is the one thing distinctive to this product.
 * Static on load; a single reveal (fade-up) plays once rather than
 * per-section scroll effects.
 */
function DoseClock() {
  const radius = 140;
  const center = 160;
  // Illustrative marker angles only — not tied to real plan data,
  // this is decorative until a plan exists.
  const markers = [8, 13, 19, 22];

  return (
    <svg
      viewBox="0 0 320 320"
      className="h-auto w-full max-w-[320px]"
      role="img"
      aria-label="Illustration of a 24-hour schedule with four medication doses placed around a clock face"
    >
      <circle cx={center} cy={center} r={radius} fill="none" stroke="#dddddd" strokeWidth="1" />
      {Array.from({ length: 24 }).map((_, hour) => {
        const angle = (hour / 24) * 2 * Math.PI - Math.PI / 2;
        const isMajor = hour % 6 === 0;
        const inner = radius - (isMajor ? 14 : 7);
        const x1 = center + inner * Math.cos(angle);
        const y1 = center + inner * Math.sin(angle);
        const x2 = center + radius * Math.cos(angle);
        const y2 = center + radius * Math.sin(angle);
        return (
          <line
            key={hour}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#999999"
            strokeWidth={isMajor ? 1.5 : 1}
          />
        );
      })}
      {markers.map((hour, i) => {
        const angle = (hour / 24) * 2 * Math.PI - Math.PI / 2;
        const x = center + radius * Math.cos(angle);
        const y = center + radius * Math.sin(angle);
        return <circle key={i} cx={x} cy={y} r="6" fill="#000000" />;
      })}
      <circle cx={center} cy={center} r="3" fill="#000000" />
    </svg>
  );
}

export default function Hero() {
  return (
    <section className="border-b border-fog bg-paper">
      <div className="mx-auto grid max-w-page grid-cols-1 items-center gap-56 px-24 py-80 md:grid-cols-[3fr_2fr] md:py-120">
        <div className="max-w-[640px] motion-safe:animate-fadeUp">
          <h1 className="font-clarkson text-[44px] font-light leading-[0.98] tracking-[-0.04em] text-obsidian sm:text-display sm:leading-display sm:tracking-display">
            Every dose,
            <br />
            accounted for.
          </h1>
          <p className="mt-24 max-w-[46ch] font-clarkson text-subheading leading-subheading tracking-subheading text-ash">
            RxLogic builds a daily medication schedule and checks it for
            interaction risk — using a rule engine and a constraint solver,
            not a language model's guess. Every placement traces back to the
            rule that made it.
          </p>
          <div className="mt-40 flex flex-wrap items-center gap-24">
            <a
              href="#build-a-plan"
              className="rounded-none border border-obsidian px-32 py-16 font-clarkson text-body-sm text-obsidian transition-colors duration-200 ease-editorial hover:bg-obsidian hover:text-paper"
            >
              Build my plan
            </a>
            <span className="font-clarkson text-caption uppercase tracking-[0.08em] text-slate">
              No account needed
            </span>
          </div>
        </div>

        <div className="flex justify-center md:justify-end">
          <DoseClock />
        </div>
      </div>
    </section>
  );
}