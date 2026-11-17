import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { ImageResponse } from 'next/og'
import { THEME } from '@/lib/theme-colors'

/** A TTF from front/assets/ (next/og needs TTF, OTF or WOFF, not the woff2 of next/font). */
export const font = (file: string) =>
  readFile(join(process.cwd(), 'assets', file))

/** The app icon: "t." in the logo face (Bricolage Grotesque 800) on the brand gradient. */
export async function appIcon(px: number, rounded = true) {
  return new ImageResponse(
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `linear-gradient(to bottom right, ${THEME.brand.from}, ${THEME.brand.to})`,
        borderRadius: rounded ? px * 0.22 : 0,
        color: THEME.brand.text,
        fontFamily: 'Bricolage Grotesque',
        fontSize: px * 0.62,
        letterSpacing: '-0.04em',
      }}
    >
      t.
    </div>,
    {
      width: px,
      height: px,
      fonts: [
        {
          name: 'Bricolage Grotesque',
          data: await font('BricolageGrotesque-800.ttf'),
          weight: 800,
        },
      ],
    }
  )
}
