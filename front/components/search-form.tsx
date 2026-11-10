'use client'

import { Search } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { pageSizeFor } from '@/lib/grid'
import { setPage, waveKeystroke } from '@/lib/waveform'

/** The results URL for a Description, with N sized to the visitor's screen. */
function searchUrl(q: string) {
  const n = pageSizeFor(
    document.documentElement.clientWidth,
    window.innerHeight
  )
  return `/?${new URLSearchParams({ q, n: String(n) })}`
}

// Resolves the hero → compact bar morph once the compact bar is on screen.
let morphed: (() => void) | undefined

/** Runs a search; the background waveform tightens until the Matches show. */
export function search(router: ReturnType<typeof useRouter>, q: string) {
  setPage('submitting')
  const url = searchUrl(q)
  // From the home page, the logo and form morph into the compact bar (View Transitions API).
  // Without support, or with reduced motion, the layout switches at once.
  if (
    !document.startViewTransition ||
    new URLSearchParams(location.search).has('q') ||
    matchMedia('(prefers-reduced-motion: reduce)').matches
  )
    return router.push(url)
  document.startViewTransition(
    () =>
      new Promise<void>((resolve) => {
        morphed = resolve
        setTimeout(resolve, 1000) // never hold the page frozen on a slow navigation
        router.push(url)
      })
  )
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
        document
          .getElementsByTagName('html')[0]
          .classList.remove('no-scrollbar')
        search(router, String(new FormData(event.currentTarget).get('q')))
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
          placeholder="Descreva sua música favorita..."
          defaultValue={defaultValue}
          onChange={() => waveKeystroke()}
          required
          maxLength={300}
          autoComplete="off"
          className="
                border-0 text-base md:text-xs
                bg-linear-to-br from-field-start to-field-end
                focus:border placeholder:text-muted-foreground"
        />

        <Button
          type="submit"
          variant="secondary"
          aria-label={compact ? 'Pesquisar' : undefined}
          className={cn(
            'cursor-pointer brand-gradient text-zinc-900 hover:[--brand-from:var(--color-indigo-300)] transition-colors',
            compact ? 'shrink-0 max-sm:size-9' : 'w-full'
          )}
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
