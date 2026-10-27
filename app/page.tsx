import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import SearchBox from '@/components/ui/searchbox'

export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <Card
        className="
          min-w-md rounded-3xl 
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

          <SearchBox width="100%">
            <>
              <Input
                id="input-search"
                type="text"
                placeholder="Descreva sua música favorita..."
                maxLength={300}
                className="
                  border-0 text-white
                  bg-linear-to-br from-indigo-950 to-mauve-700 
                  focus:border placeholder:text-zinc-400"
              />

              <Button
                variant="secondary"
                className="w-full cursor-pointer bg-linear-to-br from-indigo-200 to-mauve-200 hover:from-indigo-300 transition-colors"
              >
                Pesquisar
              </Button>
            </>
          </SearchBox>
        </div>
      </Card>
    </main>
  )
}
