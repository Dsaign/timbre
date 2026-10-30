'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { pageSizeFor } from '@/lib/grid'

// Without JavaScript the form submits natively with only q, and the page uses N = 24.
export function SearchForm({ defaultValue }: { defaultValue?: string }) {
  const router = useRouter()
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        const q = String(new FormData(event.currentTarget).get('q'))
        const n = pageSizeFor(
          document.documentElement.clientWidth,
          window.innerHeight
        )
        router.push(`/?${new URLSearchParams({ q, n: String(n) })}`)
      }}
    >
      <Field>
        <Input
          name="q"
          type="text"
          aria-label="Descreva sua música favorita"
          placeholder="Descreva sua música favorita..."
          defaultValue={defaultValue}
          required
          maxLength={300}
          className="
                border-0 text-white
                bg-linear-to-br from-indigo-950 to-mauve-700
                focus:border placeholder:text-zinc-400"
        />

        <Button
          type="submit"
          variant="secondary"
          className="w-full cursor-pointer bg-linear-to-br from-indigo-200 to-mauve-200 hover:from-indigo-300 transition-colors"
        >
          Pesquisar
        </Button>
      </Field>
    </form>
  )
}
