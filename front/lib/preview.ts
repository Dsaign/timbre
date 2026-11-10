import 'server-only'
import { back } from '@/lib/api/client'
import type { components } from '@/lib/api/schema'

/** Song ID → its Spotify track and cover. A Song missing here, or with a null track, is not available. */
export type Previews = Record<
  string,
  components['schemas']['Preview'] | undefined
>

/** Never rejects: a failed lookup only hides Preview (the next search tries again). */
export async function lookupPreviews(songIds: string[]): Promise<Previews> {
  try {
    const { data } = await back.POST('/preview', {
      body: { song_ids: songIds },
    })
    return Object.fromEntries((data ?? []).map((p) => [p.song_id, p]))
  } catch {
    return {}
  }
}
