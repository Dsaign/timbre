# UI primitives are Radix UI, icons are Lucide

The project started from shadcn's `base-lyra` style, which builds on Base UI (`@base-ui/react`) with Phosphor icons. The project owner chose Radix UI as the primitive library and Lucide as the icon set instead, so shadcn components are generated in a Radix-based style with `lucide-react`. Base UI and Phosphor are removed rather than kept side by side, so there is one way to build a component. Brand marks (Spotify, GitHub, MusicBrainz) are not icons: they use each brand's official SVG asset, as their guidelines require.
