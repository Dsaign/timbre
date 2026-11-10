import type { Metadata } from 'next'
import { ThemeProvider } from 'next-themes'
import { Inter } from 'next/font/google'
import { PreviewPlayer } from '@/components/preview-player'
import { SiteFooter } from '@/components/site-footer'
import { WaveformBackground } from '@/components/waveform-background'
import { ENTRANCE_VARS } from '@/lib/entrance'
import { LAYOUT_VARS } from '@/lib/grid'
import './globals.css'

const inter = Inter({
  style: 'normal',
  weight: ['400', '600'],
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'timbre',
  description: 'Descreva sua música favorita e descubra músicas parecidas.',
}

export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    // suppressHydrationWarning: next-themes sets the theme class on <html> before React hydrates.
    <html
      lang="pt-br"
      suppressHydrationWarning
      className={`antialiased no-scrollbar ${inter.className}`}
    >
      {/* Room at the bottom so the floating player (80 px, 12 px up) never covers the last cards or the footer. */}
      <body
        style={{ ...LAYOUT_VARS, ...ENTRANCE_VARS }}
        className="flex min-h-screen flex-col has-data-[dock=open]:pb-26"
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
