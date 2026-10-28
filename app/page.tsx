import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

export default function Home() {
  return (
    <Card
      className="
        w-full lg:max-w-md md:min-w-md rounded-3xl 
        bg-linear-to-br from-indigo-800 to-mauve-500
        p-px text-center text-white
        has-[:hover]:shadow-[-5px_-5px_40px_1px_var(--color-indigo-500)]
        has-[:hover]:shadow-indigo-500/10
        transition-shadow
        duration-500
        "
    >
      <div className="rounded-[calc(1.5rem-2px)] bg-black/60 p-6">
        <h1 className="mb-8 mt-3 text-6xl">timbre.</h1>

        {/* shortcut: GET to the same page only puts ?q= in the URL, nothing reads it yet; point action at the search when it exists */}
        <form>
          <Field>
            <Input
              name="q"
              type="text"
              aria-label="Descreva sua música favorita"
              placeholder="Descreva sua música favorita..."
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
      </div>
    </Card>
  )
}
