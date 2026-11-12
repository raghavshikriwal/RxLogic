import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Restores expected scroll behaviour for a client-routed app:
 *  - new route            -> jump to top
 *  - route with #fragment -> smooth-scroll to that element once it has rendered
 * BrowserRouter does neither on its own, so "New plan" from /history would
 * otherwise land at the top of the page instead of at the form.
 */
export default function ScrollManager() {
  const { pathname, hash, key } = useLocation();

  useEffect(() => {
    if (hash) {
      const id = decodeURIComponent(hash.slice(1));
      const frame = requestAnimationFrame(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      return () => cancelAnimationFrame(frame);
    }
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    return undefined;
  }, [pathname, hash, key]);

  return null;
}
