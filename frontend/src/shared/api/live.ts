/**
 * How often a screen that two devices work on together refreshes: the complaint and case pages, the inbox and the
 * alerts bell. TanStack pauses the interval while the tab is hidden, so a background tab costs nothing.
 */
export const LIVE_MS = 10_000;
