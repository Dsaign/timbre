import { ImageResponse } from 'next/og'
import { font } from '@/lib/og'
import { THEME } from '@/lib/theme-colors'

export const alt =
  'timbre. Descreva o clima de uma música e encontre outras com a mesma sensação.'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

/** The link preview (Open Graph, and X through the same image): the hero's logo and line. */
export default async function OpenGraphImage() {
  const { bgCenter, bgMid, bgEdge, foreground } = THEME.light
  return new ImageResponse(
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 24,
        // The Light theme's page background.
        background: `radial-gradient(ellipse at 50% 55%, ${bgCenter} 0%, ${bgMid} 60%, ${bgEdge} 100%)`,
        color: foreground,
        fontFamily: 'Inter',
      }}
    >
      <div
        style={{
          fontFamily: 'Bricolage Grotesque',
          fontSize: 180,
          fontWeight: 800,
          letterSpacing: '-0.04em',
        }}
      >
        timbre.
      </div>
      <div style={{ fontSize: 40, maxWidth: 900, textAlign: 'center' }}>
        Descreva o clima de uma música e encontre outras com a mesma sensação.
      </div>
    </div>,
    {
      ...size,
      fonts: [
        {
          name: 'Bricolage Grotesque',
          data: await font('BricolageGrotesque-800.ttf'),
          weight: 800,
        },
        { name: 'Inter', data: await font('Inter-400.ttf'), weight: 400 },
      ],
    }
  )
}
