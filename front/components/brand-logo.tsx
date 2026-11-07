import Image from 'next/image'

/** A brand's official logo file: the black one in the light theme, the white one in the dark. */
export function BrandLogo({
  name,
  width,
  height,
}: {
  name: string
  width: number
  height: number
}) {
  return (['black', 'white'] as const).map((color) => (
    <Image
      key={color}
      src={`/${name}-${color}.svg`}
      alt=""
      width={width}
      height={height}
      unoptimized
      // Eager: a hidden lazy image keeps Firefox from ever reaching networkidle.
      loading="eager"
      className={color === 'black' ? 'dark:hidden' : 'hidden dark:block'}
    />
  ))
}
