'use client'

import { Music, Pause, Play } from 'lucide-react'
import Image from 'next/image'
import {
  createContext,
  use,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { BrandLogo } from '@/components/brand-logo'
import { Button } from '@/components/ui/button'
import type { Previews } from '@/lib/preview'
import { setPlaying as setWavePlaying } from '@/lib/waveform'

// The parts of Spotify's iFrame API that timbre uses:
// https://developer.spotify.com/documentation/embeds/references/iframe-api
type PlaybackEvent = { data: { playingURI?: string; isPaused?: boolean } }
type EmbedController = {
  loadUri(uri: string): void
  play(): void
  togglePlay(): void
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

type Playing = { uri?: string; paused: boolean }
const PlayPreview = createContext<{
  play: (trackId: string) => void
  playing: Playing
}>({ play: () => {}, playing: { paused: true } })

/** One Spotify Embed floating at the bottom; every card's Preview plays in it. */
export function PreviewPlayer({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  // Only play and pause are listened to; position, duration and artwork never are.
  const [playing, setPlaying] = useState<Playing>({ paused: true })
  const playingNow = useRef(playing)
  useEffect(() => {
    playingNow.current = playing
  }, [playing])
  // The background waveform follows the same play/pause signal (ADR 0001: nothing else).
  useEffect(() => setWavePlaying(!playing.paused), [playing.paused])
  const slot = useRef<HTMLDivElement>(null)
  const controller = useRef<Promise<EmbedController>>(null)

  const play = useCallback((trackId: string) => {
    const uri = `spotify:track:${trackId}`
    setOpen(true)
    if (controller.current) {
      const { uri: current, paused } = playingNow.current
      controller.current.then((c) => {
        // The card that is playing pauses; any other card starts its own track.
        if (current === uri && !paused) return c.togglePlay()
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
    <PlayPreview value={{ play, playing }}>
      {children}
      {/* Exactly the embed (80 px, Spotify's smallest), nothing drawn over it. overflow-hidden
          with the embed's own 12 px radius trims only the empty corners around it (ADR 0001). */}
      <section
        aria-label="Prévia no Spotify"
        data-dock={open ? 'open' : 'closed'}
        data-playing-uri={playing.uri}
        data-paused={playing.paused}
        className="fixed inset-x-0 bottom-3 z-10 mx-auto h-20 w-[min(100%_-_2rem,max(36rem,60vw),48rem)] overflow-hidden rounded-xl data-[dock=closed]:hidden [&_iframe]:block [&_iframe]:border-0"
      >
        <div ref={slot} className="h-20" />
      </section>
    </PlayPreview>
  )
}

/** The 64 px box of a card's cover, its placeholder and its skeleton. */
export const COVER_BOX = 'size-16 shrink-0 rounded-[4px]'

/** The Song's album cover from Spotify (shown as is: Spotify's artwork rules), or a placeholder. */
export function PreviewCover({
  previews,
  songId,
}: {
  previews: Promise<Previews>
  songId: string
}) {
  const preview = use(previews)[songId]
  const src = preview?.spotify_track_id && preview.album_image_url
  if (src)
    return (
      // Empty alt: the title sits right next to it.
      <Image
        src={src}
        alt=""
        width={64}
        height={64}
        unoptimized
        className={`${COVER_BOX} object-contain`}
      />
    )
  return <CoverPlaceholder />
}

export function CoverPlaceholder() {
  return (
    <div
      className={`${COVER_BOX} grid place-items-center border border-zinc-300 bg-zinc-100 text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-white`}
    >
      <Music aria-hidden className="size-6" />
    </div>
  )
}

/** A card's Preview button and Spotify link, or "Prévia indisponível". */
export function PreviewControls({
  previews,
  songId,
  title,
}: {
  previews: Promise<Previews>
  songId: string
  title: string
}) {
  const { play, playing } = use(PlayPreview)
  const trackId = use(previews)[songId]?.spotify_track_id
  if (!trackId)
    return (
      <p className="py-3 text-xs text-muted-foreground">Prévia indisponível</p>
    )
  const playingThis =
    playing.uri === `spotify:track:${trackId}` && !playing.paused
  return (
    <div className="flex items-center justify-between gap-2">
      {/* The name starts with the visible text (WCAG 2.5.3), so it follows the state. */}
      <Button
        type="button"
        variant="secondary"
        aria-label={`${playingThis ? 'Tocando' : 'Prévia de'} ${title}`}
        onClick={() => play(trackId)}
        className="cursor-pointer rounded-md transition-colors hover:brand-gradient hover:text-zinc-900"
      >
        {playingThis ? <Pause aria-hidden /> : <Play aria-hidden />}
        {playingThis ? 'Tocando' : 'Prévia'}
      </Button>
      {/* Spotify branding: the official icon (21 px or more), black or white, on a link to the
          track (docs/research/spotify-platform-terms.md §6). 44 px touch target. */}
      <a
        href={`https://open.spotify.com/track/${trackId}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Listen on Spotify: ${title}`}
        className="-mr-2.5 grid size-11 shrink-0 place-items-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-foreground"
      >
        <BrandLogo name="spotify-icon" width={24} height={23} />
      </a>
    </div>
  )
}
