import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  blendSeconds,
  waveTarget,
  type Theme,
  type WaveState,
} from './waveform'

const STATES: WaveState[] = [
  'idle',
  'typing',
  'submitting',
  'matches',
  'playing',
]
const THEMES: Theme[] = ['light', 'dark']

describe.each(THEMES)('waveTarget, %s theme', (theme) => {
  const shape = (state: WaveState) => waveTarget(state, theme, false).shape

  it('idle drifts slowly, without ripples', () => {
    expect(shape('idle').speed).toBeGreaterThan(0)
    expect(shape('idle').ripple).toBe(0)
  })

  it('typing ripples', () => {
    expect(shape('typing').ripple).toBeGreaterThan(0)
  })

  it('submitting tightens the ribbon and lines it up horizontally', () => {
    expect(shape('submitting').width).toBeLessThan(shape('idle').width)
    expect(shape('submitting').amplitude).toBeLessThan(shape('idle').amplitude)
    expect(shape('submitting').flatten).toBeGreaterThan(0.5)
  })

  it('Matches relax it again', () => {
    expect(shape('matches').width).toBeGreaterThan(shape('submitting').width)
    expect(shape('matches').flatten).toBe(0)
  })

  it('a playing Preview is warmer and livelier, bokeh included', () => {
    expect(shape('playing').amplitude).toBeGreaterThan(shape('idle').amplitude)
    expect(shape('playing').wander).toBeGreaterThan(shape('idle').wander) // bokeh too
    const warm = (state: WaveState) =>
      Object.values(waveTarget(state, theme, false).colors).filter(
        (token) => token === '--warm'
      ).length
    expect(warm('playing')).toBeGreaterThan(0)
    for (const state of STATES)
      if (state !== 'playing') expect(warm(state)).toBe(0)
  })

  it('with reduced motion the ribbon stays still and only colours change', () => {
    const still = STATES.map((s) => waveTarget(s, theme, true))
    for (const t of still) {
      expect(t.shape).toEqual(still[0].shape) // brightness included
      expect(t.shape.speed).toBe(0)
      expect(t.shape.ripple).toBe(0)
    }
    expect(still[STATES.indexOf('playing')].colors).not.toEqual(
      still[STATES.indexOf('idle')].colors
    )
  })
})

it.each([
  // [state, amplitude, speed, width, flatten, ripple, brightness, wander]
  ['idle', 0.16, 0.22, 0.32, 0, 0, 1, 1],
  ['typing', 0.16, 0.22, 0.32, 0, 1, 1.05, 1],
  ['submitting', 0.04, 0.5, 0.07, 0.9, 0, 1.1, 0.6],
  ['matches', 0.18, 0.16, 0.38, 0, 0, 0.95, 0.9],
  ['playing', 0.3, 0.4, 0.36, 0, 0, 1.1, 2.2],
] as const)(
  '%s has its tuned shape',
  (state, amplitude, speed, width, flatten, ripple, brightness, wander) => {
    expect(waveTarget(state, 'dark', false).shape).toEqual({
      amplitude,
      speed,
      width,
      flatten,
      ripple,
      brightness,
      wander,
    })
  }
)

it('each theme has its own colours', () => {
  for (const state of STATES)
    expect(waveTarget(state, 'light', false).colors).not.toEqual(
      waveTarget(state, 'dark', false).colors
    )
})

it('a stopped Preview eases back over about 2 s, to the Matches or to idle', () => {
  expect(blendSeconds('playing', 'matches')).toBeCloseTo(2, 0)
  expect(blendSeconds('playing', 'idle')).toBeCloseTo(2, 0)
  expect(blendSeconds('idle', 'playing')).toBeLessThan(2)
})

describe('waveState', () => {
  // Fresh module state for every test.
  let wave: typeof import('./waveform')
  beforeEach(async () => {
    vi.resetModules()
    wave = await import('./waveform')
  })

  it('is idle at first', () => {
    expect(wave.waveState(0)).toBe('idle')
  })

  it('tightens on submit and relaxes when the Matches show', () => {
    wave.setPage('submitting')
    expect(wave.waveState(0)).toBe('submitting')
    wave.setPage('matches')
    expect(wave.waveState(0)).toBe('matches')
  })

  it('a playing Preview wins over a new search until it stops', () => {
    wave.setPlaying(true)
    wave.setPage('submitting')
    expect(wave.waveState(0)).toBe('playing')
    wave.setPage('matches')
    expect(wave.waveState(0)).toBe('playing')
    wave.setPlaying(false)
    expect(wave.waveState(0)).toBe('matches')
  })

  it('a stopped Preview with no Matches on screen goes back to idle', () => {
    wave.setPlaying(true)
    wave.setPlaying(false)
    expect(wave.waveState(0)).toBe('idle')
  })

  it('is "typing" just after a keystroke, but never over a playing Preview', () => {
    wave.waveKeystroke(1000)
    expect(wave.waveState(1100)).toBe('typing')
    expect(wave.waveState(5000)).toBe('idle')
    wave.setPlaying(true)
    expect(wave.waveState(1100)).toBe('playing')
  })

  it('keeps only the last KEYSTROKES keystrokes, newest first', () => {
    for (let t = 0; t < wave.KEYSTROKES + 3; t++) wave.waveKeystroke(t)
    expect(wave.keystrokes).toHaveLength(wave.KEYSTROKES)
    expect(wave.keystrokes[0]).toBe(wave.KEYSTROKES + 2)
  })
})
