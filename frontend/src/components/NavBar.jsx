import { NavLink } from 'react-router-dom';

const NAV_LINKS = [
  { to: '/', label: 'Plan', end: true },
  { to: '/history', label: 'History', end: false },
];

/**
 * Persistent top nav. Obsidian background per the design system's
 * "nav bar on scroll" surface role — kept permanently dark rather than
 * transitioning on scroll, since RxLogic is a single utility screen,
 * not a marketing page with a light hero to contrast against.
 */
export default function NavBar() {
  return (
    <header className="sticky top-0 z-50 h-[72px] bg-obsidian">
      <div className="mx-auto flex h-full max-w-page items-center justify-between px-24">
        <NavLink to="/" className="font-clarkson text-subheading font-medium text-paper" aria-label="RxLogic home">
          RxLogic
        </NavLink>

        <nav className="flex items-center gap-32" aria-label="Primary">
          <ul className="flex items-center gap-8 rounded-full bg-charcoal p-8">
            {NAV_LINKS.map(({ to, label, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    [
                      'block rounded-full px-16 py-8 font-clarkson text-body-sm font-medium transition-colors duration-200 ease-editorial',
                      isActive ? 'bg-paper text-obsidian' : 'text-ash hover:text-paper',
                    ].join(' ')
                  }
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>

          <a
            href="#build-a-plan"
            className="hidden rounded-none border border-paper px-16 py-8 font-clarkson text-body-sm text-paper transition-colors duration-200 ease-editorial hover:bg-paper hover:text-obsidian sm:block"
          >
            New plan
          </a>
        </nav>
      </div>
    </header>
  );
}