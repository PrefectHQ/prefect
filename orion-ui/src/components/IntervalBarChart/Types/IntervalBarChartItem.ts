export type IntervalBarChartItem<T = unknown> = {
  interval_start: string
  interval_end: string
  value: number
  data?: T
}
