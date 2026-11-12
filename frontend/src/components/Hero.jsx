/**
 * Landing-page hero for RxLogic.
 *
 * The clock is intentionally illustrative: its markers are not connected to
 * a user's medication data and must never be interpreted as a real schedule.
 */
function DoseClock() {
  const radius = 132;
  const center = 160;
  const markers = [8, 13, 19, 22];

  return (
    <svg
      viewBox="0 0 320 320"
      className="rx-hero-clock"
      role="img"
      aria-labelledby="dose-clock-title dose-clock-description"
    >
      <title id="dose-clock-title">Illustrative 24-hour schedule clock</title>
      <desc id="dose-clock-description">
        A decorative clock face with four markers, representing possible dose
        positions. It does not show a real medication schedule.
      </desc>
      <circle className="rx-hero-clock__ring" cx={center} cy={center} r={radius} />
      <circle className="rx-hero-clock__ring rx-hero-clock__ring--inner" cx={center} cy={center} r="104" />
      {Array.from({ length: 24 }, (_, hour) => {
        const angle = (hour / 24) * 2 * Math.PI - Math.PI / 2;
        const major = hour % 6 === 0;
        const inner = radius - (major ? 15 : 8);
        return (
          <line
            key={hour}
            className={major ? 'rx-hero-clock__tick rx-hero-clock__tick--major' : 'rx-hero-clock__tick'}
            x1={center + inner * Math.cos(angle)}
            y1={center + inner * Math.sin(angle)}
            x2={center + radius * Math.cos(angle)}
            y2={center + radius * Math.sin(angle)}
          />
        );
      })}
      {markers.map((hour) => {
        const angle = (hour / 24) * 2 * Math.PI - Math.PI / 2;
        return (
          <circle
            key={hour}
            className="rx-hero-clock__marker"
            cx={center + radius * Math.cos(angle)}
            cy={center + radius * Math.sin(angle)}
            r="6"
          />
        );
      })}
      <circle className="rx-hero-clock__hub" cx={center} cy={center} r="4" />
    </svg>
  );
}

const PILLARS = [
  {
    number: '01',
    title: 'Rule-based checks',
    description: 'Interaction checks are handled by explicit symbolic rules.',
  },
  {
    number: '02',
    title: 'Constraint scheduling',
    description: 'Timing is arranged around the constraints supplied to the system.',
  },
  {
    number: '03',
    title: 'Traceable reasoning',
    description: 'The application can show the rules behind its scheduling decisions.',
  },
];

export default function Hero() {
  return (
    <section className="rx-hero">
      <div className="rx-hero__backdrop" aria-hidden="true" />
      <div className="rx-hero__inner">
        <div className="rx-hero__copy">
          <p className="rx-hero__eyebrow">
            <span className="rx-hero__eyebrow-dot" aria-hidden="true" />
            Neuro-symbolic medication scheduling
          </p>

          <h1 className="rx-hero__title">
            Every dose,
            <br />
            <span>accounted for.</span>
          </h1>

          <p className="rx-hero__description">
            RxLogic builds a daily medication schedule and checks it for
            interaction risk using a rule engine and a constraint solver —
            not a language model's guess. Every placement can be traced back
            to the rule that informed it.
          </p>

          <div className="rx-hero__actions">
            <a href="#build-a-plan" className="rx-hero__primary">
              Build my plan
              <span aria-hidden="true">↗</span>
            </a>
            <a href="#how-rxlogic-works" className="rx-hero__secondary">
              Explore the approach
            </a>
          </div>

          <p className="rx-hero__note">
            Educational demonstrator · No account needed
          </p>
        </div>

        <div className="rx-hero__visual">
          <div className="rx-hero__visual-glow" aria-hidden="true" />
          <div className="rx-hero__clock-card">
            <div className="rx-hero__clock-topline">
              <span>24-HOUR VIEW</span>
              <span className="rx-hero__clock-status">
                <span aria-hidden="true" />
                Illustrative
              </span>
            </div>
            <DoseClock />
            <div className="rx-hero__clock-footer">
              <span className="rx-hero__clock-footer-mark" aria-hidden="true">✳</span>
              <span>Structured timing. Explainable decisions.</span>
            </div>
          </div>
          <div className="rx-hero__floating-label" aria-hidden="true">
            <span className="rx-hero__floating-label-icon">✓</span>
            Rule-guided reasoning
          </div>
        </div>
      </div>

      <div className="rx-hero__principles" id="how-rxlogic-works">
        <div className="rx-hero__principles-heading">
          <span>THE RXLOGIC APPROACH</span>
          <p>Designed to make the reasoning easier to inspect.</p>
        </div>
        <div className="rx-hero__principles-grid">
          {PILLARS.map((pillar) => (
            <article className="rx-hero__principle" key={pillar.number}>
              <span className="rx-hero__principle-number">{pillar.number}</span>
              <div>
                <h2>{pillar.title}</h2>
                <p>{pillar.description}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
