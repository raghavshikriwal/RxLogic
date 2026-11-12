import { useEffect, useState } from 'react';

/**
 * True once the page has scrolled past `threshold` pixels.
 * Passive listener; state only changes when the boolean flips, so scrolling
 * does not re-render subscribers on every frame.
 */
export default function useScrolled(threshold = 8) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const update = () => setScrolled(window.scrollY > threshold);
    update();
    window.addEventListener('scroll', update, { passive: true });
    return () => window.removeEventListener('scroll', update);
  }, [threshold]);

  return scrolled;
}
