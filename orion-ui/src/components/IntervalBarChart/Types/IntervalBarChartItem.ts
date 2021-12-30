export type IntervalBarChartItem<T = unknown> = {
  interval_start: Date
  interval_end: Date
  value: number
  data?: T
}
