import 'server-only'
import { back } from '@/lib/api/client'

/** Song ID → Spotify track ID. A Song that is null or missing is not available. */
export type Previews = Record<string, string | null>

/** Never rejects: a failed lookup only hides Preview (the next search tries again). */
export async function lookupPreviews(songIds: string[]): Promise<Previews> {
  try {
    const { data } = await back.POST('/preview', {
      body: { song_ids: songIds },
    })
    return Object.fromEntries(
      (data ?? []).map((p) => [p.song_id, p.spotify_track_id])
    )
  } catch {
    return {}
  }
}
