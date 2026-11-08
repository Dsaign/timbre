import type { Metadata } from 'next'
import { ThemeProvider } from 'next-themes'
import { Inter } from 'next/font/google'
import { PreviewPlayer } from '@/components/preview-player'
import { SiteFooter } from '@/components/site-footer'
import { ThemeToggle } from '@/components/theme-toggle'
import './globals.css'

const inter = Inter({
  style: 'normal',
  weight: '400',
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
      className={`antialiased ${inter.className}`}
    >
      {/* Room at the bottom so the docked player never covers the last cards or the footer. */}
      <body className="flex min-h-screen flex-col bg-linear-to-br from-indigo-100 to-mauve-200 has-data-[dock=open]:pb-28 dark:from-indigo-950 dark:to-mauve-700">
        {/* Default storage is localStorage (key "theme"); next-themes sets no cookie. */}
        <ThemeProvider attribute="class" disableTransitionOnChange>
          <header className="flex justify-end px-3 pt-3">
            <ThemeToggle />
          </header>
          <main className="grid flex-1 place-items-center">
            <PreviewPlayer>{children}</PreviewPlayer>
          </main>
          <SiteFooter />
        </ThemeProvider>
      </body>
    </html>
  )
}
