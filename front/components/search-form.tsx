'use client'

import { Search } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { useDockOpen } from '@/components/preview-player'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { currentScreen, pageSizeFor } from '@/lib/grid'
import { setPage, waveKeystroke } from '@/lib/waveform'

// Resolves the hero → compact bar morph once the compact bar is on screen.
let morphed: (() => void) | undefined

type Pending = { q: string; n: number }
let showPending: ((search: Pending) => void) | undefined
// The search waiting for its morph to finish; only this one may still be sent.
let waiting: object | undefined

/** The hero's PendingSearch registers here: it shows the compact bar and skeletons on demand. */
export function onPendingSearch(show: (search: Pending) => void) {
  showPending = show
  return () => {
    if (showPending !== show) return
    showPending = undefined
    waiting = undefined // the visitor left the hero: the waiting search is never sent
  }
}

/** Runs a search; the background waveform tightens until the Matches show. */
export function search(
  router: ReturnType<typeof useRouter>,
  q: string,
  dockOpen: boolean
) {
  setPage('submitting')
  // N sized to the visitor's screen.
  const n = pageSizeFor(currentScreen(dockOpen))
  const url = `/?${new URLSearchParams({ q, n: String(n) })}`
  // From the hero, the logo and form morph into the compact bar (View Transitions API), drawn
  // with skeletons by PendingSearch before any request; the search is sent once the morph is
  // over. It is sent at once without support, with reduced motion, from the results' compact
  // bar (q in the URL), or while an earlier search still waits for its morph: this one
  // replaces it, so only the latest Description is sent.
  const show = showPending
  const replacing = waiting
  waiting = undefined
  if (
    !show ||
    replacing ||
    !document.startViewTransition ||
    new URLSearchParams(location.search).has('q') ||
    matchMedia('(prefers-reduced-motion: reduce)').matches
  )
    return router.push(url)
  const morph = document.startViewTransition(
    () =>
      new Promise<void>((resolve) => {
        morphed = resolve
        setTimeout(resolve, 1000) // never hold the page frozen
        show({ q: q.trim(), n })
      })
  )
  const self = {}
  waiting = self
  const send = () => {
    if (waiting !== self) return // replaced, or the visitor left
    waiting = undefined
    router.push(url)
  }
  morph.finished.then(send, send)
}

// Without JavaScript the form submits natively with only q, and the page uses N = 24.
export function SearchForm({
  defaultValue,
  compact = false,
}: {
  defaultValue?: string
  compact?: boolean
}) {
  const router = useRouter()
  const dockOpen = useDockOpen()
  // The compact bar is on screen: a pending morph can capture it now.
  useEffect(() => {
    if (!compact) return
    morphed?.()
    morphed = undefined
  }, [compact])
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        search(
          router,
          String(new FormData(event.currentTarget).get('q')),
          dockOpen
        )
      }}
      className={cn(
        '[view-transition-name:search]',
        compact && 'min-w-0 flex-1'
      )}
    >
      <Field orientation={compact ? 'horizontal' : 'vertical'}>
        <Input
          name="q"
          type="text"
          aria-label="Descreva sua música favorita"
          placeholder="Descreva sua música favorita…"
          defaultValue={defaultValue}
          onChange={() => waveKeystroke()}
          required
          maxLength={300}
          autoComplete="off"
          // A solid --field-bg inside a 1 px gradient border (field-start → field-end).
          // In the hero it spans the panel, like the button below it.
          className={cn(
            'text-base md:text-xs border-transparent [background:linear-gradient(var(--field-bg),var(--field-bg))_padding-box,linear-gradient(to_bottom_right,var(--field-start),var(--field-end))_border-box] placeholder:text-muted-foreground',
            compact && 'max-w-xl'
          )}
        />

        <Button
          type="submit"
          variant="brand"
          aria-label={compact ? 'Pesquisar' : undefined}
          className={cn(compact ? 'shrink-0 max-sm:size-9' : 'w-full')}
        >
          {compact && <Search aria-hidden className="sm:hidden" />}
          <span className={compact ? 'max-sm:hidden' : undefined}>
            Pesquisar
          </span>
        </Button>
      </Field>
    </form>
  )
}
