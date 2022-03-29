import { State, StateName } from '@/types/states'

export type IStateHistoryResponse = {
  state_type: State,
  state_name: StateName,
  count_runs: number,
  sum_estimated_run_time: number,
  sum_estimated_lateness: number,
}