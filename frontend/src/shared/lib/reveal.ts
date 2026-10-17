/** Brings a section into view after React has drawn the change, and moves focus there for keyboard users. */
export function revealSection(id: string): void {
  requestAnimationFrame(() => {
    const el = document.getElementById(id);
    if (!el) return;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' });
    el.focus({ preventScroll: true });
  });
}
