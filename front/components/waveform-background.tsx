'use client'

import { useEffect, useRef } from 'react'
import {
  blendSeconds,
  KEYSTROKES,
  keystrokes,
  setPage,
  waveState,
  waveTarget,
  type Shape,
  type WaveState,
} from '@/lib/waveform'
import { ENTRANCE_MS } from '@/lib/entrance'

const RIBBONS = 2
const ROWS = 46
const COLS = 160
const BOKEH = 120
const SHOW_UI_AFTER_MS = 1000 // the UI shows even if the background isn't ready by then

/** Starts the UI's entrance (globals.css) once; later mounts then just appear. */
function showUi() {
  const html = document.documentElement
  if (html.dataset.ui) return
  html.dataset.ui = 'ready'
  setTimeout(() => (html.dataset.ui = 'done'), ENTRANCE_MS)
}

// =============================================
// VERTEX SHADER
// =============================================

const VERTEX = `#version 300 es
precision highp float;

uniform float uDensity, uPhase, uAmplitude, uWidth, uFlatten;
uniform float uRipple, uBrightness, uWander, uAspect, uDpr, uMaxSize;
uniform float uKeyAge[${KEYSTROKES}];

uniform vec3 uRibbon, uEdge, uBokeh;
uniform bool uIsBokeh;

out vec4 vColor;
out float vBlur;
out float vGlow;

// ---------------------------------------------
// Camera
// ---------------------------------------------

// Profundidade do plano de foco (0 = centro da tela).
const float FOCUS_DEPTH = 0.04;

// Pixels de desfoque por unidade de distancia do foco.
const float APERTURE = 30.0;

// Tamanho de uma particula nitida (px CSS).
const float MIN_SIZE = 1.6;

// 2.0 = conservacao fisica de energia.
// Menor = partes desfocadas mais brilhantes.
const float ENERGY = 1.3;

// Quanto a profundidade escala posicao e tamanho.
const float PERSPECTIVE = 0.35;

// Inclinacao da fita em profundidade:
// esquerda perto da camera, direita longe.
const float DEPTH_SLOPE = 0.42;

// ---------------------------------------------
// Movimento
// ---------------------------------------------

const float FLOW_SPEED = 0.014;
const float WAVE_SPEED = 0.55;
const float TWIST_SPEED = 0.30;

const float TAU = 6.28318530718;

// Hash inteiro. O hash com sin() perde precisao em IDs
// altos e repete padroes, reforcando a grade na fita.
float hash(float n) {
  uint x = floatBitsToUint(n);
  x ^= x >> 16; x *= 0x7feb352du;
  x ^= x >> 15; x *= 0x846ca68bu;
  x ^= x >> 16;
  return float(x) / 4294967295.0;
}

// Degrade horizontal em tres cores:
// uRibbon (esquerda) -> uBokeh (centro) -> uEdge (direita).
vec3 particleGradient(float x) {
  float leftToCenter = smoothstep(-0.95, 0.25, x);
  float centerToRight = smoothstep(-0.05, 1.0, x);

  vec3 color = mix(uRibbon, uBokeh, leftToCenter);
  color = mix(color, uEdge, centerToRight);

  return color;
}

void main() {
  float id = float(gl_VertexID);
  float t = uPhase;
  float still = 1.0 - uFlatten;

  vec2 pos;
  vec3 color;
  float alpha, sizePx;

  // =========================================
  // BACKGROUND BOKEH PARTICLES
  // =========================================

  if (uIsBokeh) {
    float s1 = hash(id * 1.31 + 3.0);
    float s2 = hash(id * 2.17 + 11.0);
    float s3 = hash(id * 3.03 + 29.0);
    float s4 = hash(id * 4.71 + 53.0);

    // Concentra o bokeh na faixa da fita, com alguns espalhados.
    float x = s1 * 2.8 - 1.4;
    float y = (s2 - 0.5) * mix(0.35, 1.3, s4 * s4) - 0.03 - 0.05 * x;

    // Flutuacao lenta e continua, sem tremor: um fluxo para a direita (que da a volta)
    // mais um vaguear que cresce com uWander, mais vivo enquanto uma Previa toca.
    x = mod(x + 1.4 + t * 0.06 * mix(0.5, 1.5, s3), 2.8) - 1.4;
    x += 0.06 * uWander * sin(t * 0.9 * mix(0.6, 1.4, s3) + s1 * 40.0);
    y += 0.045 * uWander * sin(t * 0.7 * mix(0.6, 1.4, s4) + s2 * 40.0);

    // -1 = muito perto da camera, +1 = muito longe.
    float depth = s3 * 2.0 - 1.0;
    float persp = 1.0 / (1.0 + depth * PERSPECTIVE);

    pos = vec2(x, y) * persp;

    // Circulo de confusao.
    float coc = abs(depth - FOCUS_DEPTH);
    float sizeCss = (2.0 + 90.0 * coc * coc) * persp;

    sizePx = min(sizeCss * uDpr, uMaxSize);
    float effCss = sizePx / uDpr;

    alpha = 0.9 * pow(2.0 / effCss, 0.45) * mix(0.5, 1.0, s4);

    // Some nas bordas, onde o fluxo da a volta.
    alpha *= smoothstep(1.4, 1.15, abs(x));

    // Pontos pequenos cintilam.
    float tw = 0.5 + 0.5 * sin(t * mix(1.0, 2.5, s2) + s1 * 60.0);
    alpha *= mix(0.4 + 0.6 * tw, 1.0, smoothstep(3.0, 10.0, effCss));

    color = particleGradient(pos.x + (s4 - 0.5) * 0.8);

    vBlur = smoothstep(3.0, 14.0, effCss);
    vGlow = mix(0.9, 1.2, s2);

  } else {

    // =========================================
    // MAIN PARTICLE RIBBONS
    // =========================================

    float perRibbon = ${ROWS * COLS}.0;

    float r = floor(id / perRibbon);
    float k = id - r * perRibbon;

    float row = floor(k / ${COLS}.0);
    float col = k - row * ${COLS}.0;

    float s1 = hash(id * 1.173 + 42.0);
    float s2 = hash(id * 2.371 + 17.0);
    float s3 = hash(id * 3.713 + 91.0);
    float s4 = hash(id * 5.119 + 7.0);
    float s5 = hash(id * 6.427 + 13.0);

    // Posicao ao longo (u) e atraves (v) da fita.
    // O jitter dentro da celula elimina a grade e cada
    // particula flui com velocidade levemente diferente.
    float u = (col + s1) / ${COLS}.0;
    u = fract(u + t * FLOW_SPEED * mix(0.8, 1.2, s2));

    float v = (row + s3) / ${ROWS}.0;

    float x = mix(-1.45, 1.45, u);

    // Linha central: duas ondas longas em sentidos opostos.
    float wave =
      0.65 * sin(x * 1.7 - t * WAVE_SPEED + r * 2.3)
      + 0.35 * sin(x * 3.1 + t * WAVE_SPEED * 0.7 + r * 1.1);

    float y = -0.06 * x - 0.02 + uAmplitude * still * wave;

    // A fita e uma lamina que torce em torno do proprio eixo.
    float theta = x * 1.5 - t * TWIST_SPEED + r * 2.0
      + 0.4 * sin(x * 0.8 + t * 0.2);

    float width = uWidth
      * (1.0 - 0.35 * r)
      * (0.8 + 0.2 * sin(x * 1.3 - t * 0.25 + r));

    float across = (v - 0.5) * width;

    y += across * cos(theta);
    float z = across * sin(theta) * still;

    // Deriva individual lenta e pequena (respiracao, nao tremor).
    float ph = s1 * TAU;
    float sp = mix(0.5, 1.0, s2);
    float motion = 0.4 + 0.6 * still;

    vec3 drift = vec3(
      sin(t * 0.31 * sp + ph),
      sin(t * 0.27 * sp + ph * 1.7),
      sin(t * 0.23 * sp + ph * 2.3)
    ) * 0.0035 * motion;

    // Algumas particulas se soltam da lamina.
    float stray = step(0.965, s4);

    drift += stray * vec3(
      0.0,
      (s3 - 0.5) * 0.14 + 0.02 * sin(t * 0.4 + ph),
      (s5 - 0.5) * 0.5
    );

    x += drift.x;
    y += drift.y;
    z += drift.z;

    // =========================================
    // KEYBOARD INTERACTION
    // =========================================

    float ripple = 0.0;

    for (int i = 0; i < ${KEYSTROKES}; i++) {
      float age = uKeyAge[i];

      if (age < 2.5) {
        float pulse = exp(-pow((x + 1.3 - age * 1.2) * 3.0, 2.0));
        float fade = 1.0 - pow(age / 2.5, 3.0);

        ripple += pulse * fade;
      }
    }

    ripple = min(ripple, 1.0);
    // y += uRipple * 0.005 * ripple * still;

    // =========================================
    // DEPTH OF FIELD
    // =========================================

    // Profundidade vem principalmente de x (a fita atravessa
    // o plano de foco) e da torcao. A segunda fita fica mais
    // atras, portanto mais desfocada.
    float depth = x * DEPTH_SLOPE + z + r * 0.3;
    float persp = 1.0 / (1.0 + depth * PERSPECTIVE);

    pos = vec2(x, y) * persp;

    // Distancia ao plano de foco vira tamanho.
    float coc = abs(depth - FOCUS_DEPTH);
    float sparkle = step(0.993, s5);

    float sizeCss = (
      MIN_SIZE * mix(0.8, 1.25, s2) * (1.0 + sparkle)
      + APERTURE * coc
    ) * persp;

    // Energia calculada com o tamanho JA limitado por uMaxSize.
    sizePx = min(sizeCss * uDpr, uMaxSize);
    float effCss = sizePx / uDpr;

    float energy = pow(MIN_SIZE / effCss, ENERGY);

    // =========================================
    // PARTICLE LIGHTING
    // =========================================

    alpha = 0.85 * energy * mix(0.55, 1.0, hash(id + 1.0));

    // Some nas pontas para esconder o loop do fluxo.
    alpha *= smoothstep(0.0, 0.08, u) * smoothstep(1.0, 0.92, u);

    // Bordas da lamina mais luminosas.
    float edge = smoothstep(0.75, 1.0, abs(v - 0.5) * 2.0);
    alpha *= 1.0 + 1.5 * edge;

    // Brilhos que cintilam.
    float tw = 0.5 + 0.5 * sin(t * mix(1.5, 3.0, s1) + ph * 3.0);
    alpha *= 1.0 + sparkle * 3.0 * tw * tw;

    alpha *= 1.0 + uRipple * 0.5 * ripple;
    alpha *= uDensity;

    // =========================================
    // COLOR GRADIENT
    // =========================================

    color = particleGradient(pos.x);

    // O trecho em foco fica levemente mais claro.
    float inFocus = 1.0 - smoothstep(0.0, 0.25, coc);
    color *= 1.0 + 0.25 * inFocus + 0.2 * edge;

    // Na fita o desfoque vira halo suave (vBlur ate 0.45), para
    // as particulas se fundirem num brilho continuo em vez de
    // aparecerem como discos separados.
    vBlur = 0.45 * smoothstep(2.5, 12.0, effCss);
    vGlow = mix(0.9, 1.15, s3) + sparkle * 0.5;
  }

  gl_Position = vec4(
    pos.x,
    pos.y * uAspect,
    0.0,
    1.0
  );

  gl_PointSize = sizePx;

  vColor = vec4(
    color,
    alpha * uBrightness
  );
}
`

// =============================================
// FRAGMENT SHADER
// =============================================

// vBlur = 0 -> ponto nitido com brilho gaussiano
// vBlur = 1 -> disco de bokeh com borda suave e aro mais claro
const FRAGMENT = `#version 300 es
precision highp float;

in vec4 vColor;
in float vBlur;
in float vGlow;

out vec4 outColor;

void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float d = length(p);

  if (d > 1.0) discard;

  // Ponto em foco.
  float focused = exp(-d * d * 4.0);

  // Disco desfocado: borda vai ficando mais definida
  // conforme o desfoque aumenta, como numa lente real.
  float edgeWidth = mix(0.6, 0.2, vBlur);
  float disc = 1.0 - smoothstep(1.0 - edgeWidth, 1.0, d);

  // Aro de lente: bokeh real e um pouco mais claro na borda.
  disc *= 1.0 + 0.35 * smoothstep(0.5, 0.95, d) * vBlur;

  float shape = mix(focused, disc, smoothstep(0.0, 0.6, vBlur));

  float alpha = clamp(vColor.a * shape, 0.0, 1.0);

  // Premultiplied alpha.
  outColor = vec4(
    vColor.rgb * alpha * vGlow,
    alpha
  );
}
`

// =============================================
// TYPES
// =============================================

type Blend = {
  shape: Shape
  colors: Record<string, number[]>
}

const uniformName = (key: string) => `u${key[0].toUpperCase()}${key.slice(1)}`

// =============================================
// WAVEFORM STATE
// =============================================

export function WaveformState({
  state,
}: {
  state: Parameters<typeof setPage>[0]
}) {
  useEffect(() => setPage(state), [state])

  return null
}

// =============================================
// WEBGL BACKGROUND
// =============================================

export function WaveformBackground() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current!
    const fallback = setTimeout(showUi, SHOW_UI_AFTER_MS)

    const gl = canvas.getContext('webgl2', {
      antialias: false,
      alpha: true,
      premultipliedAlpha: true,
    })

    if (!gl) {
      clearTimeout(fallback)
      return showUi()
    }

    const program = gl.createProgram()

    if (!program) return

    const shaders: WebGLShader[] = []

    for (const [type, source] of [
      [gl.VERTEX_SHADER, VERTEX],
      [gl.FRAGMENT_SHADER, FRAGMENT],
    ] as const) {
      const shader = gl.createShader(type)!

      gl.shaderSource(shader, source)
      gl.compileShader(shader)

      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error(
          'Waveform shader compilation error:',
          gl.getShaderInfoLog(shader)
        )

        gl.deleteShader(shader)

        for (const previous of shaders) {
          gl.deleteShader(previous)
        }

        gl.deleteProgram(program)

        return
      }

      shaders.push(shader)
      gl.attachShader(program, shader)
    }

    gl.linkProgram(program)

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error(
        'Waveform program linking error:',
        gl.getProgramInfoLog(program)
      )

      for (const shader of shaders) {
        gl.deleteShader(shader)
      }

      gl.deleteProgram(program)

      return
    }

    gl.useProgram(program)

    for (const shader of shaders) {
      gl.deleteShader(shader)
    }

    gl.bindVertexArray(gl.createVertexArray())

    gl.enable(gl.BLEND)
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)

    const uniform = (name: string) => gl.getUniformLocation(program, name)

    const maxPointSize = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE)[1]

    gl.uniform1f(uniform('uMaxSize'), maxPointSize)

    // =========================================
    // CSS COLOR CONVERSION
    // =========================================

    const probe = document.createElement('canvas').getContext('2d', {
      willReadFrequently: true,
    })!

    const rgb = (token: string) => {
      probe.clearRect(0, 0, 1, 1)

      probe.fillStyle = getComputedStyle(document.documentElement)
        .getPropertyValue(token)
        .trim()

      probe.fillRect(0, 0, 1, 1)

      return [...probe.getImageData(0, 0, 1, 1).data.slice(0, 3)].map(
        (c) => c / 255
      )
    }

    // =========================================
    // ANIMATION STATE
    // =========================================

    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)')

    let key = ''
    let drawn: WaveState | undefined

    let seconds = 1

    let goal: Blend
    let now: Blend | undefined

    let phase = 0
    let last = performance.now()
    let raf = 0

    // =========================================
    // RENDER LOOP
    // =========================================

    const frame = (time: number) => {
      raf = 0

      if (document.hidden) return

      const dt = Math.min((time - last) / 1000, 0.1)

      last = time

      const theme = document.documentElement.classList.contains('dark')
        ? 'dark'
        : 'light'

      const state = waveState(time)

      // Update target when state or theme changes.
      if (key !== `${state} ${theme} ${reducedMotion.matches}`) {
        key = `${state} ${theme} ${reducedMotion.matches}`

        const { shape, colors } = waveTarget(
          state,
          theme,
          reducedMotion.matches
        )

        goal = {
          shape,
          colors: Object.fromEntries(
            Object.entries(colors).map(([name, token]) => [name, rgb(token)])
          ),
        }

        if (drawn && drawn !== state) {
          seconds = blendSeconds(drawn, state)
        }

        drawn = state
      }

      // Smooth transition between states.
      const k = now ? 1 - Math.exp((-4 * dt) / seconds) : 1

      const mix = (a: number, b: number) => a + (b - a) * k

      const prev = now ?? goal

      now = {
        shape: Object.fromEntries(
          Object.entries(goal.shape).map(([name, value]) => [
            name,
            mix(prev.shape[name as keyof Shape], value),
          ])
        ) as Shape,

        colors: Object.fromEntries(
          Object.entries(goal.colors).map(([name, colors]) => [
            name,
            colors.map((c, i) => mix(prev.colors[name][i], c)),
          ])
        ),
      }

      // Animation phase.
      phase += dt * now.shape.speed

      // =========================================
      // CANVAS SIZE
      // =========================================

      const dpr = Math.min(devicePixelRatio, 2)

      const width = Math.round(canvas.clientWidth * dpr)

      const height = Math.round(canvas.clientHeight * dpr)

      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width
        canvas.height = height

        gl.viewport(0, 0, width, height)
      }

      // =========================================
      // UNIFORMS
      // =========================================

      gl.uniform1f(
        uniform('uAspect'),
        Math.min(Math.max(width / height, 0.9), 1.8)
      )

      gl.uniform1f(uniform('uDpr'), dpr)

      gl.uniform1f(
        uniform('uDensity'),
        Math.min(Math.max(canvas.clientWidth / 1280, 0.3), 1)
      )

      gl.uniform1f(uniform('uPhase'), phase)

      for (const [name, value] of Object.entries(now.shape)) {
        const location = uniform(uniformName(name))

        if (location !== null) {
          gl.uniform1f(location, value)
        }
      }

      for (const [name, colors] of Object.entries(now.colors)) {
        const location = uniform(uniformName(name))

        if (location !== null) {
          gl.uniform3fv(location, colors)
        }
      }

      gl.uniform1fv(
        uniform('uKeyAge'),
        Array.from({ length: KEYSTROKES }, (_, i) => {
          if (keystrokes[i] === undefined) return 99

          const x = Math.min((time - keystrokes[i]) / 750, 1)
          const eased = x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2

          return eased * 5
        })
      )

      // =========================================
      // DRAW
      // =========================================

      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)

      // Main ribbons.
      gl.uniform1i(uniform('uIsBokeh'), 0)

      gl.drawArrays(gl.POINTS, 0, RIBBONS * ROWS * COLS)

      // Independent moving background particles.
      gl.uniform1i(uniform('uIsBokeh'), 1)

      gl.drawArrays(gl.POINTS, 0, BOKEH)

      canvas.dataset.ready = ''
      showUi()

      raf = requestAnimationFrame(frame)
    }

    // =========================================
    // VISIBILITY
    // =========================================

    const resume = () => {
      if (document.hidden || raf) return

      last = performance.now()

      raf = requestAnimationFrame(frame)
    }

    document.addEventListener('visibilitychange', resume)

    resume()

    // =========================================
    // CLEANUP
    // =========================================

    return () => {
      clearTimeout(fallback)
      cancelAnimationFrame(raf)

      document.removeEventListener('visibilitychange', resume)

      gl.deleteProgram(program)
    }
  }, [])

  return (
    <canvas
      ref={ref}
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 size-full opacity-0 transition-opacity duration-1000 data-ready:opacity-100"
    />
  )
}
