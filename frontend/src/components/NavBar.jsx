import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import Logo from './Logo.jsx';
import useScrolled from '../hooks/useScrolled.js';

const NAV_LINKS = [
  { to: '/', label: 'Plan', end: true },
  { to: '/history', label: 'History', end: false },
];

const MOBILE_LINKS = [...NAV_LINKS, { to: '/#build-a-plan', label: 'New plan', end: false }];

const DESKTOP_QUERY = '(min-width: 768px)';

/**
 * Global navigation.
 * - Translucent, blurred bar that gains a hairline once the page scrolls.
 * - Below `md`, links move into a full-screen menu with a morphing toggle.
 *   The menu closes on route change, Escape, and when the viewport widens;
 *   page scroll is locked while it is open.
 */
export default function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const scrolled = useScrolled();
  const { pathname } = useLocation();

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return undefined;

    const onKeyDown = (event) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    const media = window.matchMedia(DESKTOP_QUERY);
    const onChange = (event) => {
      if (event.matches) setMenuOpen(false);
    };

    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKeyDown);
    media.addEventListener('change', onChange);

    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', onKeyDown);
      media.removeEventListener('change', onChange);
    };
  }, [menuOpen]);

  const barSurface =
    scrolled || menuOpen
      ? 'border-hairline/70 bg-paper/80 backdrop-blur-xl backdrop-saturate-[180%]'
      : 'border-transparent bg-paper/0';

  return (
    <header
      className={`sticky top-0 z-50 h-nav border-b transition-[background-color,border-color] duration-400 ease-apple ${barSurface}`}
    >
      <div className="mx-auto flex h-full max-w-page items-center justify-between px-24">
        <Link
          to="/"
          aria-label="RxLogic home"
          className="flex items-center gap-8 font-display text-caption font-semibold text-ink"
        >
          <Logo />
          RxLogic
        </Link>

        <nav className="hidden items-center gap-32 md:flex" aria-label="Primary">
          <ul className="flex items-center gap-32">
            {NAV_LINKS.map(({ to, label, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `text-micro transition-colors duration-300 ease-apple ${
                      isActive ? 'text-ink' : 'text-deep-gray hover:text-ink'
                    }`
                  }
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
          <Link
            to="/#build-a-plan"
            className="rounded-pill bg-electric-blue px-12 py-4 text-micro font-medium text-paper transition-colors duration-300 ease-apple hover:bg-blue-hover active:bg-blue-press"
          >
            New plan
          </Link>
        </nav>

        <button
          type="button"
          className="-mr-8 flex h-44 w-44 items-center justify-center md:hidden"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          aria-controls="mobile-menu"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className="relative block h-12 w-20" aria-hidden="true">
            <span
              className={`absolute left-0 h-[1.5px] w-20 bg-ink transition-all duration-400 ease-apple ${
                menuOpen ? 'top-[5px] rotate-45' : 'top-0'
              }`}
            />
            <span
              className={`absolute left-0 h-[1.5px] w-20 bg-ink transition-all duration-400 ease-apple ${
                menuOpen ? 'top-[5px] -rotate-45' : 'top-[10px]'
              }`}
            />
          </span>
        </button>
      </div>

      <div
        id="mobile-menu"
        className={`fixed inset-x-0 top-[var(--nav-height)] h-[calc(100dvh-var(--nav-height))] bg-paper/95 backdrop-blur-xl transition-[opacity,visibility] duration-400 ease-apple md:hidden ${
          menuOpen ? 'visible opacity-100' : 'invisible opacity-0'
        }`}
      >
        <nav className="px-24 pt-24" aria-label="Mobile">
          <ul>
            {MOBILE_LINKS.map(({ to, label, end }, index) => (
              <li
                key={to}
                className={`border-b border-hairline/70 transition-[opacity,transform] duration-600 ease-apple-out ${
                  menuOpen ? 'translate-y-0 opacity-100' : '-translate-y-8 opacity-0'
                }`}
                style={{ transitionDelay: menuOpen ? `${80 + index * 60}ms` : '0ms' }}
              >
                <NavLink
                  to={to}
                  end={end}
                  className="block py-16 font-display text-body-lg font-semibold text-ink"
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
