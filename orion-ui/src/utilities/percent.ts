export type Percent = `${number}%`

export function toPercent(value: number): Percent {
  return `${value}%`
}

export function calculatePercent(
  unit: number,
  total: number,
  decimals = 0
): Percent {
  const percent = (unit / total) * 100
  const rounded = percent.toFixed(decimals)
  const value = parseFloat(rounded)

  return toPercent(value)
}
