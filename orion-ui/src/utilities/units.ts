export type PercentString = `${number}%`

export function toPercentString(value: number): PercentString {
  return `${value}%`
}

export function calculatePercent(
  unit: number,
  total: number,
  decimals = 0,
): PercentString {
  const percent = unit / total * 100
  const rounded = percent.toFixed(decimals)
  const value = parseFloat(rounded)

  return toPercentString(value)
}
