import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import Logo from './Logo.jsx';
import useScrolled from '../hooks/useScrolled.js';

const NAV_LINKS = [
  { to: '/', label: 'Plan', end: true },
  { to: '/history', label: 'History', end: false },
];

const MOBILE_LINKS = [...NAV_LINKS, { to: '/#build-a-plan', label: 'Create a plan', end: false }];
const DESKTOP_QUERY = '(min-width: 768px)';

function closeOnNavigation(setMenuOpen) {
  return () => setMenuOpen(false);
}

/**
 * Responsive application navigation.
 * Keeps the existing routes and destinations while improving active states,
 * mobile-menu dismissal, and the visual hierarchy of the app shell.
 */
export default function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const scrolled = useScrolled();
  const { pathname, hash } = useLocation();

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname, hash]);

  useEffect(() => {
    if (!menuOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
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
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKeyDown);
      media.removeEventListener('change', onChange);
    };
  }, [menuOpen]);

  const surfaceClass = scrolled || menuOpen ? 'app-header--scrolled' : '';

  return (
    <header className={`app-header ${surfaceClass}`}>
      <div className="app-header__inner">
        <Link to="/" aria-label="RxLogic home" className="app-brand">
          <Logo className="app-brand__mark" />
          <span className="app-brand__name">RxLogic</span>
          <span className="app-brand__descriptor">Medication reasoning</span>
        </Link>

        <nav className="app-nav app-nav--desktop" aria-label="Primary navigation">
          <ul className="app-nav__links">
            {NAV_LINKS.map(({ to, label, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `app-nav__link${isActive ? ' is-active' : ''}`
                  }
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
          <Link to="/#build-a-plan" className="app-nav__action">
            <span aria-hidden="true">＋</span>
            New plan
          </Link>
        </nav>

        <button
          type="button"
          className={`app-menu-toggle${menuOpen ? ' is-open' : ''}`}
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={menuOpen}
          aria-controls="mobile-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span />
          <span />
        </button>
      </div>

      <div
        id="mobile-navigation"
        className={`app-mobile-menu${menuOpen ? ' is-open' : ''}`}
        aria-hidden={!menuOpen}
      >
        <nav className="app-mobile-menu__content" aria-label="Mobile navigation">
          <p className="app-mobile-menu__eyebrow">Navigate RxLogic</p>
          <ul>
            {MOBILE_LINKS.map(({ to, label, end }, index) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  tabIndex={menuOpen ? 0 : -1}
                  onClick={closeOnNavigation(setMenuOpen)}
                  className={({ isActive }) =>
                    `app-mobile-menu__link${isActive ? ' is-active' : ''}`
                  }
                  style={{ transitionDelay: menuOpen ? `${index * 55}ms` : '0ms' }}
                >
                  <span>{label}</span>
                  <span className="app-mobile-menu__arrow" aria-hidden="true">↗</span>
                </NavLink>
              </li>
            ))}
          </ul>
          <p className="app-mobile-menu__note">
            An educational demonstrator of explainable medication scheduling.
          </p>
        </nav>
      </div>
    </header>
  );
}
