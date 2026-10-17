import { useEffect, useState } from 'react';

import type { Journey } from '../model/journeys';

export const STEP_MS = 2800;

/** Pass a stable list: the journeys this viewer may see. */
export function useJourney(journeys: Journey[]) {
  const [journey, setJourney] = useState(0);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const count = journeys[journey]?.steps.length ?? 0;

  useEffect(() => {
    if (!playing) return undefined;
    const id = window.setTimeout(() => {
      if (step >= count - 1) setPlaying(false);
      else setStep(step + 1);
    }, STEP_MS);
    return () => window.clearTimeout(id);
  }, [playing, step, count]);

  return {
    journeys,
    journey,
    step,
    playing,
    count,
    selectJourney: (index: number) => { setPlaying(false); setJourney(index); setStep(0); },
    goTo: (index: number) => { setPlaying(false); setStep(Math.max(0, Math.min(count - 1, index))); },
    open: (journeyIndex: number, stepIndex: number) => { setPlaying(false); setJourney(journeyIndex); setStep(stepIndex); },
    toggle: () => {
      if (!playing && step >= count - 1) setStep(0);
      setPlaying(!playing);
    },
  };
}

export type JourneyControl = ReturnType<typeof useJourney>;
