import { BrandLogo } from '@/components/brand-logo'

const SOURCES = {
  MusicBrainz: 'https://musicbrainz.org',
  AcousticBrainz: 'https://acousticbrainz.org',
  ListenBrainz: 'https://listenbrainz.org',
  Spotify: 'https://www.spotify.com',
}

// "MusicBrainz, AcousticBrainz, ListenBrainz e Spotify", each name a separate link.
const CREDITS = new Intl.ListFormat('pt-BR').formatToParts(Object.keys(SOURCES))

/** Credits the data sources and links to the public repository. */
export function SiteFooter() {
  return (
    // Full foreground, not muted: the credits sit over the vignette and must stay AA.
    <footer
      data-enter="4"
      data-site-footer
      className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 px-4 py-6 text-xs text-foreground"
    >
      <p>
        Dados de{' '}
        {CREDITS.map(({ type, value }, i) =>
          type === 'element' ? (
            <a
              key={i}
              href={SOURCES[value as keyof typeof SOURCES]}
              className="underline underline-offset-2"
            >
              {value}
            </a>
          ) : (
            value
          )
        )}
        .
      </p>
      {/* GitHub's official mark (GitHub Invertocat, from github.com/logos), black or white. */}
      <a href="https://github.com/Dsaign/timbre" aria-label="timbre no GitHub">
        <BrandLogo name="github-invertocat" width={24.5} height={24} />
      </a>
    </footer>
  )
}
