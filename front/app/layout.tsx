import type { Metadata, Viewport } from 'next'
import { ThemeProvider } from 'next-themes'
import { Bricolage_Grotesque, Inter } from 'next/font/google'
import { PreviewPlayer } from '@/components/preview-player'
import { SiteFooter } from '@/components/site-footer'
import { WaveformBackground } from '@/components/waveform-background'
import { ENTRANCE_VARS } from '@/lib/entrance'
import { LAYOUT_VARS } from '@/lib/grid'
import { THEME } from '@/lib/theme-colors'
import './globals.css'

const inter = Inter({
  style: 'normal',
  weight: ['400', '600'],
  subsets: ['latin'],
})

// The display face: the logo and the card titles (font-display).
const bricolage = Bricolage_Grotesque({
  weight: ['600', '800'],
  subsets: ['latin'],
  variable: '--font-bricolage',
})

export const metadata: Metadata = {
  title: 'timbre',
  description: 'Descreva sua música favorita e descubra músicas parecidas.',
  // The link preview uses app/opengraph-image for X too.
  twitter: { card: 'summary_large_image' },
}

// The browser chrome follows the page background's edge (--bg-edge).
export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: THEME.light.bgEdge },
    { media: '(prefers-color-scheme: dark)', color: THEME.dark.bgEdge },
  ],
}

export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    // suppressHydrationWarning: next-themes sets the theme class on <html> before React hydrates.
    <html
      lang="pt-br"
      suppressHydrationWarning
      className={`antialiased no-scrollbar ${inter.className} ${bricolage.variable}`}
    >
      {/* After a search (main[data-shell]) the page is a fixed 100dvh shell: bar, scrolling
          cards area, open dock, footer. Only the cards area scrolls. */}
      <body
        style={{ ...LAYOUT_VARS, ...ENTRANCE_VARS }}
        className="flex min-h-screen flex-col has-data-shell:h-dvh has-data-shell:min-h-0 has-data-shell:overflow-hidden"
      >
        {/* Default storage is localStorage (key "theme"); next-themes sets no cookie. */}
        <ThemeProvider attribute="class" disableTransitionOnChange>
          <WaveformBackground />
          {/* The page renders its own header (theme toggle, search bar) and main. */}
          <PreviewPlayer>{children}</PreviewPlayer>
          <SiteFooter />
        </ThemeProvider>
      </body>
    </html>
  )
}
