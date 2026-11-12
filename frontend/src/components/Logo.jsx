/** RxLogic mark: a 24-hour dial with one dose marker. Matches public/favicon.svg. */
export default function Logo({ className = 'h-24 w-24' }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true" focusable="false">
      <rect width="64" height="64" rx="15" fill="#1d1d1f" />
      <circle cx="32" cy="32" r="17" fill="none" stroke="#fff" strokeWidth="3" />
      <path
        d="M32 21v11l7 4"
        fill="none"
        stroke="#fff"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="32" cy="10" r="3.5" fill="#0071e3" />
    </svg>
  );
}
