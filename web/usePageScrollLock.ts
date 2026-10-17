import { useLayoutEffect } from 'react';

let owners = 0;
let originalOverflow = '';

/** A drawer-to-dialog handoff must not unlock or permanently lock the page. */
export function usePageScrollLock(locked: boolean) {
  useLayoutEffect(() => {
    if (!locked) return;
    if (owners++ === 0) originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { if (--owners === 0) document.body.style.overflow = originalOverflow; };
  }, [locked]);
}
