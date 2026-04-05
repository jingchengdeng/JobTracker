import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Bridge Vitest fake timers into the jest-shaped API that @testing-library/dom
// uses to detect and advance fake timers inside waitFor().
// Without this, waitFor() falls back to real setInterval polling and the
// overall-timeout setTimeout (which is faked) never fires — causing hangs.
Object.defineProperty(globalThis, "jest", {
  configurable: true,
  get() {
    return {
      advanceTimersByTime: (ms: number) => vi.advanceTimersByTime(ms),
    };
  },
});
