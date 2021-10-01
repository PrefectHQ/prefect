export type StateBucket = {
  state_type: string
  state_name: string
  count_runs: number
  sum_estimated_run_time: number
  sum_estimated_lateness: number
}

export type StateBuckets = StateBucket[]

export interface Bucket {
  interval_start: string
  interval_end: string
  states: StateBuckets
}

export type Buckets = Bucket[]
