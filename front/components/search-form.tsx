'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
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

/** Runs a search; the background waveform tightens until the Matches show. */
export function search(router: ReturnType<typeof useRouter>, q: string) {
  setPage('submitting')
  router.push(searchUrl(q))
}

// Without JavaScript the form submits natively with only q, and the page uses N = 24.
export function SearchForm({ defaultValue }: { defaultValue?: string }) {
  const router = useRouter()
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        search(router, String(new FormData(event.currentTarget).get('q')))
      }}
    >
      <Field>
        <Input
          name="q"
          type="text"
          aria-label="Descreva sua música favorita"
          placeholder="Descreva sua música favorita..."
          defaultValue={defaultValue}
          onChange={() => waveKeystroke()}
          required
          maxLength={300}
          className="
                border-0 text-base md:text-xs
                bg-linear-to-br from-field-start to-field-end
                focus:border placeholder:text-muted-foreground"
        />

        {/* Intentionally fixed: the brand gradient stays light in both themes, so its text stays dark. */}
        <Button
          type="submit"
          variant="secondary"
          className="w-full cursor-pointer bg-linear-to-br from-indigo-200 to-mauve-200 text-zinc-900 hover:from-indigo-300 transition-colors"
        >
          Pesquisar
        </Button>
      </Field>
    </form>
  )
}
