'use client'

import { Play } from 'lucide-react'
import Image from 'next/image'
import { createContext, use, useCallback, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import type { Previews } from '@/lib/preview'

// The parts of Spotify's iFrame API that timbre uses:
// https://developer.spotify.com/documentation/embeds/references/iframe-api
type PlaybackEvent = { data: { playingURI?: string; isPaused?: boolean } }
type EmbedController = {
  loadUri(uri: string): void
  play(): void
  addListener(
    event: 'playback_started' | 'playback_update',
    listener: (e: PlaybackEvent) => void
  ): void
}
type IFrameAPI = {
  createController(
    element: HTMLElement,
    options: { uri: string; width: string; height: number },
    callback: (controller: EmbedController) => void
  ): void
}
declare global {
  interface Window {
    onSpotifyIframeApiReady?: (api: IFrameAPI) => void
  }
}

let iframeApi: Promise<IFrameAPI> | undefined
function loadIframeApi() {
  iframeApi ??= new Promise((resolve) => {
    window.onSpotifyIframeApiReady = resolve
    const script = document.createElement('script')
    script.src = 'https://open.spotify.com/embed/iframe-api/v1'
    script.async = true
    script.onerror = () => (iframeApi = undefined) // the next click tries again
    document.body.append(script)
  })
  return iframeApi
}

const PlayPreview = createContext<(trackId: string) => void>(() => {})

/** One Spotify Embed docked at the bottom; every card's Preview plays in it. */
export function PreviewPlayer({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  // Only play and pause are listened to; position, duration and artwork never are.
  const [playing, setPlaying] = useState<{ uri?: string; paused: boolean }>({
    paused: true,
  })
  const slot = useRef<HTMLDivElement>(null)
  const controller = useRef<Promise<EmbedController>>(null)

  const play = useCallback((trackId: string) => {
    const uri = `spotify:track:${trackId}`
    setOpen(true)
    if (controller.current) {
      controller.current.then((c) => {
        c.loadUri(uri)
        c.play()
      })
      return
    }
    controller.current = loadIframeApi().then(
      (api) =>
        new Promise((resolve) => {
          // The API replaces this element with its iframe, so React never owns it.
          const element = document.createElement('div')
          slot.current?.append(element)
          api.createController(
            element,
            { uri, width: '100%', height: 80 },
            (c) => {
              c.addListener('playback_started', ({ data }) =>
                setPlaying((p) => ({ ...p, uri: data.playingURI }))
              )
              c.addListener('playback_update', ({ data }) =>
                setPlaying((p) =>
                  p.paused === data.isPaused
                    ? p
                    : { ...p, paused: data.isPaused ?? true }
                )
              )
              c.play()
              resolve(c)
            }
          )
        })
    )
    controller.current.catch(() => (controller.current = null))
  }, [])

  return (
    <PlayPreview value={play}>
      {children}
      <section
        aria-label="Prévia no Spotify"
        data-dock={open ? 'open' : 'closed'}
        data-playing-uri={playing.uri}
        data-paused={playing.paused}
        className="fixed inset-x-0 bottom-0 z-10 bg-black/60 p-2 backdrop-blur-md data-[dock=closed]:hidden"
      >
        <div ref={slot} className="mx-auto h-20 max-w-5xl" />
      </section>
    </PlayPreview>
  )
}

/** A card's Preview button and "LISTEN ON SPOTIFY" link, or nothing when not available. */
export function PreviewControls({
  previews,
  songId,
  title,
}: {
  previews: Promise<Previews>
  songId: string
  title: string
}) {
  const play = use(PlayPreview)
  const trackId = use(previews)[songId]
  if (!trackId) return null
  return (
    <div className="flex items-end justify-between gap-2">
      <Button
        type="button"
        variant="secondary"
        aria-label={`Prévia de ${title}`}
        onClick={() => play(trackId)}
        className="cursor-pointer rounded-md"
      >
        <Play aria-hidden />
        Prévia
      </Button>
      {/* Spotify branding: full logo at 70 px or more, monochrome off black/white, and
          one of the guideline's link texts (docs/research/spotify-platform-terms.md). */}
      <a
        href={`https://open.spotify.com/track/${trackId}`}
        target="_blank"
        rel="noopener noreferrer"
        className="flex flex-col items-end gap-1 text-[10px] font-semibold tracking-wide text-white hover:underline"
      >
        <Image
          src="/spotify-full-logo-white.svg"
          alt=""
          width={80}
          height={22}
          unoptimized
        />
        LISTEN ON SPOTIFY
      </a>
    </div>
  )
}
