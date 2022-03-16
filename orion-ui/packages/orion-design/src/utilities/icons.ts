export type IconSizeMultiplier = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 9 | 10
export type IconSize = 'xs' | 'sm' | 'md' | 'lg' | `${IconSizeMultiplier}x`

export function getIconSizeClass(size: IconSize): `pi-${IconSize}` {
  return `pi-${size}`
}
