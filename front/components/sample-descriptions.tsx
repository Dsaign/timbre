'use client'

import { useRouter } from 'next/navigation'
import { useDockOpen } from '@/components/preview-player'
import { search } from '@/components/search-form'
import { Button } from '@/components/ui/button'

// Owner-approved (ticket 06).
const SAMPLES = [
  'violão calmo para estudar',
  'guitarra suja e voz rouca, clima de estrada à noite',
  'something dark and electronic to focus',
  'músicas alegres e dançantes para uma festa',
  'sad piano ballad, slow and quiet',
  'rock pesado e agressivo com bateria forte',
]

/** Sample Descriptions as links: one click fills the input and runs the search. */
export function SampleDescriptions() {
  const router = useRouter()
  const dockOpen = useDockOpen()
  return (
    <ul
      aria-label="Exemplos de descrição"
      className="flex max-w-2xl flex-wrap justify-center gap-2"
    >
      {SAMPLES.map((q) => (
        <li key={q}>
          <Button
            asChild
            variant="secondary"
            className="h-auto rounded-full px-3 py-1.5 whitespace-normal"
          >
            {/* Without JavaScript the plain href still searches, with N = 24. */}
            <a
              href={`/?${new URLSearchParams({ q })}`}
              onClick={(event) => {
                if (event.metaKey || event.ctrlKey || event.shiftKey) return // new tab/window
                event.preventDefault()
                search(router, q, dockOpen)
              }}
            >
              {q}
            </a>
          </Button>
        </li>
      ))}
    </ul>
  )
}
