import { Link } from 'react-router-dom';
import Logo from './Logo.jsx';

const FOOTER_LINKS = [
  { to: '/', label: 'Plan' },
  { to: '/history', label: 'History' },
];

export default function Footer() {
  return (
    <footer className="bg-canvas">
      <div className="mx-auto max-w-page px-24 pb-32 pt-48">
        <p className="max-w-[80ch] text-micro text-mid-gray">
          RxLogic is an educational demonstrator of neuro-symbolic reasoning. Schedules and
          interaction notes are generated from a rule engine and a constraint solver over a limited
          knowledge base. They are not a substitute for advice from a pharmacist or physician.
        </p>

        <div className="mt-24 flex flex-col gap-16 border-t border-hairline pt-16 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-8 text-micro text-mid-gray">
            <Logo className="h-16 w-16" />
            <span>© {new Date().getFullYear()} RxLogic</span>
          </div>
          <nav aria-label="Footer">
            <ul className="flex items-center gap-24">
              {FOOTER_LINKS.map(({ to, label }) => (
                <li key={to}>
                  <Link
                    to={to}
                    className="text-micro text-deep-gray transition-colors duration-300 ease-apple hover:text-ink"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </div>
    </footer>
  );
}
