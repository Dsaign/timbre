'use client'

import { useEffect, useState } from 'react'
import { onPendingSearch } from '@/components/search-form'
import { MatchesSkeleton, SearchedLayout } from '@/components/searched-layout'

/**
 * The hero (children) until a search starts from it. Then, before any request, the compact bar
 * and the card skeletons, so the hero can morph into them; search-form.tsx sends the search once
 * the morph has finished, and the server's results layout replaces this one.
 */
export function PendingSearch({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<{ q: string; n: number } | null>(null)
  useEffect(() => onPendingSearch(setPending), [])
  if (!pending) return children
  return (
    <SearchedLayout description={pending.q}>
      <MatchesSkeleton n={pending.n} />
    </SearchedLayout>
  )
}
