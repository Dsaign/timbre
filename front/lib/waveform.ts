/**
 * What the background waveform draws. A stopped Preview has no look of its own: the ribbon eases
 * back to whatever is under it (the Matches shape, or idle) over STOP_SECONDS.
 */
export type WaveState = 'idle' | 'typing' | 'submitting' | 'matches' | 'playing'
export type Theme = 'light' | 'dark'

/** A theme colour: the name of one of globals.css's colour variables (Tailwind's or --warm). */
type Token = `--color-${string}` | '--warm'
/** Each key is also a shader uniform: ribbon → uRibbon. The shader blends them left to right. */
type Colors = { ribbon: Token; bokeh: Token; edge: Token }

// The one palette: every waveform colour, per theme and state, taken from the theme's own tokens
// (the page background is body's in app/globals.css). Playing turns to the theme's --warm accent.
const DARK: Colors = {
  ribbon: '--color-indigo-400',
  bokeh: '--color-indigo-400',
  edge: '--color-mauve-400',
}
const LIGHT: Colors = {
  ribbon: '--color-indigo-700',
  bokeh: '--color-indigo-500',
  edge: '--color-mauve-500',
}
export const PALETTE: Record<Theme, Record<WaveState, Colors>> = {
  dark: {
    idle: DARK,
    typing: { ...DARK, ribbon: '--color-indigo-300' },
    submitting: { ...DARK, ribbon: '--color-indigo-300' },
    matches: DARK,
    playing: { ribbon: '--color-mauve-300', bokeh: '--warm', edge: '--warm' },
  },
  light: {
    idle: LIGHT,
    typing: { ...LIGHT, ribbon: '--color-indigo-600' },
    submitting: { ...LIGHT, ribbon: '--color-indigo-600' },
    matches: LIGHT,
    playing: { ribbon: '--color-mauve-500', bokeh: '--warm', edge: '--warm' },
  },
}

/**
 * The particles' shape, movement (wander: how much the bokeh wanders) and brightness per state, in
 * the shader's units (screen width ≈ 2). Each key is also a shader uniform (amplitude → uAmplitude),
 * except speed, which drives uPhase. Every state is idle plus what differs.
 */
const IDLE = {
  amplitude: 0.16,
  speed: 0.22,
  width: 0.32,
  flatten: 0,
  ripple: 0,
  brightness: 1,
  wander: 1,
}
const SHAPE: Record<WaveState, typeof IDLE> = {
  idle: IDLE,
  typing: { ...IDLE, ripple: 1, brightness: 1.05 },
  submitting: {
    ...IDLE,
    amplitude: 0.04,
    speed: 0.5,
    width: 0.07,
    flatten: 0.9,
    brightness: 1.1,
    wander: 0.6,
  },
  matches: {
    ...IDLE,
    amplitude: 0.18,
    speed: 0.16,
    width: 0.38,
    brightness: 0.95,
    wander: 0.9,
  },
  playing: {
    ...IDLE,
    amplitude: 0.3,
    speed: 0.4,
    width: 0.36,
    brightness: 1.1,
    wander: 2.2,
  },
}
export type Shape = typeof IDLE

/** How long the blend into each state takes. */
const BLEND_SECONDS: Record<WaveState, number> = {
  idle: 1,
  typing: 0.5,
  submitting: 0.6,
  matches: 1.5,
  playing: 1,
}
/** A stopped Preview eases back over about 2 s. */
const STOP_SECONDS = 2

export type WaveTarget = { shape: Shape; colors: Colors }

/** The shader parameters the waveform blends towards. Reduced motion: one still shape, colours only. */
export function waveTarget(
  state: WaveState,
  theme: Theme,
  reducedMotion: boolean
): WaveTarget {
  return {
    shape: reducedMotion ? { ...SHAPE.idle, speed: 0 } : SHAPE[state],
    colors: PALETTE[theme][state],
  }
}

/** Seconds the blend from one drawn state to the next takes. */
export function blendSeconds(from: WaveState, to: WaveState) {
  return from === 'playing' && to !== 'playing'
    ? STOP_SECONDS
    : BLEND_SECONDS[to]
}

/** How many recent keystrokes each send their own ripple (the shader's uKeyAge array). */
export const KEYSTROKES = 8
const TYPING_MS = 1500

// What the visitor is doing: the page (set by the search form and the Matches) and the Preview
// (set by the player's play/pause events) are separate, so a search never hides a playing Preview.
let page: 'idle' | 'submitting' | 'matches' = 'idle'
let playing = false
let submitTimer: ReturnType<typeof setTimeout> | undefined
/** The last KEYSTROKES keystrokes (performance.now() ms), newest first. */
export const keystrokes: number[] = []

export function setPage(next: typeof page) {
  page = next
  clearTimeout(submitTimer)
  // A search whose Matches never remount (same URL, network error) must not stay tightened.
  if (next === 'submitting')
    submitTimer = setTimeout(() => setPage('matches'), 10_000)
}

export function setPlaying(next: boolean) {
  playing = next
}

export function waveKeystroke(now = performance.now()) {
  keystrokes.unshift(now)
  keystrokes.length = Math.min(keystrokes.length, KEYSTROKES)
}

/** The state to draw. A playing Preview wins; typing shows for a moment after a keystroke. */
export function waveState(now = performance.now()): WaveState {
  if (playing) return 'playing'
  if (page !== 'submitting' && now - (keystrokes[0] ?? -Infinity) < TYPING_MS)
    return 'typing'
  return page
}
