// Theme colours as raw hex, for the places CSS variables can't reach: the app icon and the Open
// Graph image (lib/og.tsx) and the browser's theme-color (app/layout.tsx). Copies of the tokens
// in app/globals.css (--bg-*, --foreground) and the brand gradient (indigo-200 → mauve-200,
// the brand-gradient utility): change both together.
export const THEME = {
  light: {
    bgCenter: '#eef1f7',
    bgMid: '#dfe5ef',
    bgEdge: '#cfd7e5',
    foreground: '#0a0a0a',
  },
  dark: { bgEdge: '#131824' },
  brand: { from: '#c6d2ff', to: '#e7e4e7', text: '#18181b' }, // text: zinc-900
}
