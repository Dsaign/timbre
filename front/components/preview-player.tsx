'use client'

import { Music, Pause, Play } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'
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
import { LAYOUT } from '@/lib/grid'
import type { Previews } from '@/lib/preview'
import { setPlaying as setWavePlaying } from '@/lib/waveform'

// The parts of Spotify's iFrame API that timbre uses:
// https://developer.spotify.com/documentation/embeds/references/iframe-api
type PlaybackEvent = { data: { playingURI?: string; isPaused?: boolean } }
type EmbedController = {
  loadUri(uri: string): void
  play(): void
  pause(): void
  togglePlay(): void
  destroy(): void
  addListener(
    event: 'ready' | 'playback_started' | 'playback_update',
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
  iframeApi ??= new Promise((resolve, reject) => {
    window.onSpotifyIframeApiReady = resolve
    const script = document.createElement('script')
    script.src = 'https://open.spotify.com/embed/iframe-api/v1'
    script.async = true
    // Reject so the caller drops its player; clearing the cache lets the next click try again.
    script.onerror = () => {
      iframeApi = undefined
      reject(new Error('Spotify iFrame API failed to load'))
    }
    document.body.append(script)
  })
  return iframeApi
}

type Playing = { uri?: string; paused: boolean }
const PlayPreview = createContext<{
  play: (trackId: string) => void
  close: () => void
  open: boolean
  playing: Playing
}>({ play: () => {}, close: () => {}, open: false, playing: { paused: true } })

/** Whether the dock is open (it takes room the results' page size must leave). */
export const useDockOpen = () => use(PlayPreview).open

/** One Spotify Embed docked above the footer; every card's Preview plays in it. */
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
  // Safari (and maybe Firefox) block the embed's play() after a click on timbre (docs/research/
  // spotify-embed-autoplay.md): a track still silent 2 s after it is ready asks for the embed's own play.
  const [askPlay, setAskPlay] = useState(false)
  const askPlayTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const hideAskPlay = useCallback(() => {
    clearTimeout(askPlayTimer.current)
    setAskPlay(false)
  }, [])
  const armAskPlay = useCallback(() => {
    clearTimeout(askPlayTimer.current)
    // Checked when it fires: a brief isPaused:false must not cancel the prompt for a blocked play().
    askPlayTimer.current = setTimeout(
      () => setAskPlay(playingNow.current.paused),
      2000
    )
  }, [])

  const play = useCallback(
    (trackId: string) => {
      const uri = `spotify:track:${trackId}`
      setOpen(true)
      if (controller.current) {
        const { uri: current, paused } = playingNow.current
        controller.current.then((c) => {
          // The card that is playing pauses; any other card starts its own track.
          if (current === uri && !paused) return c.togglePlay()
          // loadUri reloads the embed even for the same track, and its `ready` re-arms the prompt.
          hideAskPlay()
          // The reload stops the old track; the new embed's events set the real state.
          setPlaying({ paused: true })
          c.loadUri(uri)
          c.play()
        })
        return
      }
      const created: Promise<EmbedController> = loadIframeApi().then(
        (api) =>
          new Promise((resolve) => {
            // The API replaces this element with its iframe, so React never owns it.
            const element = document.createElement('div')
            slot.current?.append(element)
            api.createController(
              element,
              { uri, width: '100%', height: LAYOUT.dock.height },
              (c) => {
                c.addListener('ready', armAskPlay)
                // Not proof of sound: the embed sends it once the track is loaded, even when the browser blocks play().
                c.addListener('playback_started', ({ data }) =>
                  setPlaying((p) => ({ ...p, uri: data.playingURI }))
                )
                c.addListener('playback_update', ({ data }) => {
                  if (data.isPaused === false) setAskPlay(false)
                  setPlaying((p) =>
                    p.paused === data.isPaused
                      ? p
                      : { ...p, paused: data.isPaused ?? true }
                  )
                })
                c.play()
                resolve(c)
              }
            )
          })
      )
      controller.current = created
      // close() may have dropped it already; never forget a newer player.
      created.catch(() => {
        if (controller.current === created) controller.current = null
      })
    },
    [armAskPlay, hideAskPlay]
  )

  // Hidden and unloaded: no audio keeps playing out of sight, with no pause report to trust
  // (Firefox CI kept data-paused="false" after pause()). The next Prévia builds a new player.
  // A player still being created is destroyed as soon as it exists.
  const close = useCallback(() => {
    setOpen(false)
    hideAskPlay()
    controller.current?.then((c) => c.destroy())
    controller.current = null
    setPlaying({ paused: true })
  }, [hideAskPlay])

  return (
    <PlayPreview value={{ play, close, open, playing }}>
      {children}
      {/* Exactly the embed (Spotify's smallest, LAYOUT.dock), nothing drawn over it, in its own
          space above the footer. overflow-hidden with the embed's own 12 px radius trims only
          the empty corners around it (ADR 0001). The play prompt floats just above it. */}
      <section
        aria-label="Prévia no Spotify"
        data-dock={open ? 'open' : 'closed'}
        data-playing-uri={playing.uri}
        data-paused={playing.paused}
        className="relative mx-auto mt-(--dock-gap) h-(--dock-height) w-[min(100%-2rem,max(36rem,60vw),48rem)] shrink-0 data-[dock=closed]:hidden [&_iframe]:block [&_iframe]:border-0"
      >
        {/* The live region stays in the DOM (never display:none) so screen readers announce the
            pill when it appears; it never takes clicks meant for the cards under it. */}
        <p
          role="status"
          className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-(--dock-gap) -translate-x-1/2 text-xs whitespace-nowrap text-foreground"
        >
          {askPlay && (
            <span className="block rounded-full bg-glass frosted px-3 py-1">
              Toque em ▶ no player do Spotify para ouvir
            </span>
          )}
        </p>
        <div
          ref={slot}
          className="h-(--dock-height) overflow-hidden rounded-xl"
        />
      </section>
    </PlayPreview>
  )
}

/** A link home that first closes the dock and unloads its player. */
export function HomeLink(props: React.ComponentProps<typeof Link>) {
  const { close } = use(PlayPreview)
  return (
    <Link
      {...props}
      onClick={(event) => {
        close()
        props.onClick?.(event)
      }}
    />
  )
}

/** On the home page the dock closes and unloads, however the visitor got there (logo, Back). */
export function ClosePreview() {
  const { close } = use(PlayPreview)
  useEffect(close, [close])
  return null
}

/** The 80 px box of a card's cover, its placeholder and its skeleton. */
export const COVER_BOX = 'size-20 shrink-0 rounded-[4px]'

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
        width={80}
        height={80}
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
      <Music aria-hidden className="size-7" />
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
      {/* The name starts with the visible text (WCAG 2.5.3), so it follows the state.
          The card's main action: the brand gradient at rest too. after: a 44 px touch target. */}
      <Button
        type="button"
        variant="brand"
        aria-label={`${playingThis ? 'Tocando' : 'Prévia de'} ${title}`}
        onClick={() => play(trackId)}
        className="relative after:absolute after:-inset-y-1.5 after:inset-x-0"
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
