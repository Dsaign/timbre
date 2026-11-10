import type { CSSProperties } from 'react'

// The one source for the UI's entrance (globals.css, [data-enter] steps 1 to 4):
// app/layout.tsx sets these as CSS variables on <body>, waveform-background.tsx times its end.
export const ENTRANCE = { stepMs: 120, fadeMs: 500, steps: 4 }

/** From the first step's start to the last step's end. */
export const ENTRANCE_MS =
  (ENTRANCE.steps - 1) * ENTRANCE.stepMs + ENTRANCE.fadeMs

/** The entrance timing as CSS variables, for <body>. */
export const ENTRANCE_VARS = {
  '--enter-step': `${ENTRANCE.stepMs}ms`,
  '--enter-fade': `${ENTRANCE.fadeMs}ms`,
} as CSSProperties
