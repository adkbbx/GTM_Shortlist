import { Fragment, useEffect, useRef, useState } from 'react';

/** Words fade up when the heading enters view (Alia's technique). Reduced motion shows them at once; the hidden state
    is also scoped to `prefers-reduced-motion: no-preference` in CSS, so text is never left invisible. */
export function Reveal({ as: Tag = 'h2', id, className, reduced, lead, accent, br = false }: { as?: 'h1' | 'h2'; id: string; className?: string; reduced: boolean; lead: string; accent: string; br?: boolean }) {
  const ref = useRef<HTMLHeadingElement>(null);
  const [shown, setShown] = useState(reduced);
  useEffect(() => {
    if (reduced) { setShown(true); return; }
    const node = ref.current; if (!node) return;
    const observer = new IntersectionObserver(entries => { if (entries[0].isIntersecting) { setShown(true); observer.disconnect(); } }, { threshold: 0.35 });
    observer.observe(node); return () => observer.disconnect();
  }, [reduced]);
  let index = 0;
  const words = (text: string) => text.split(' ').map((word, k, all) => <Fragment key={k}><span className="pl-w" style={{ ['--i' as string]: index++ }}>{word}</span>{k < all.length - 1 ? ' ' : null}</Fragment>);
  return <Tag ref={ref} id={id} className={className} data-reveal={shown ? 'shown' : 'hidden'}>{words(lead)}{br ? <br /> : ' '}<span className="pl-accent">{words(accent)}</span></Tag>;
}
