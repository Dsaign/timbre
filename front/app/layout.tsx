import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
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
    <html lang="pt-br" className={`h-full antialiased ${inter.className}`}>
      <body className="bg-zinc-900 text-zinc-300 ">
        <main className="grid min-h-screen place-items-center bg-linear-to-br from-indigo-950 to-mauve-700">
          {children}
        </main>
      </body>
    </html>
  )
}
