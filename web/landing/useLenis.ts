import { useEffect, useRef, useSyncExternalStore } from 'react';
import Lenis from 'lenis';
import 'lenis/dist/lenis.css';

/** Smooth scrolling for the public landing page only. Never created under reduced motion; destroyed on unmount. */
export function useLenis(enabled: boolean) {
  const lenis = useRef<Lenis | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const header = parseFloat(getComputedStyle(document.documentElement).fontSize) * 4.25;
    const instance = new Lenis({ autoRaf: true, lerp: 0.1, anchors: { offset: -(header + 8) } });
    lenis.current = instance;
    return () => { instance.destroy(); lenis.current = null; };
  }, [enabled]);
  return lenis;
}

const motionQuery = () => window.matchMedia('(prefers-reduced-motion: reduce)');
export function usePrefersReducedMotion() {
  return useSyncExternalStore(changed => {
    const query = motionQuery(); query.addEventListener('change', changed);
    return () => query.removeEventListener('change', changed);
  }, () => motionQuery().matches, () => false);
}
