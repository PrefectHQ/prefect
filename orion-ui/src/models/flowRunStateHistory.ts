import { StateType, StateName } from '@/types/states'

export type IFlowRunStateHistory = {
  state_type: StateType
  state_name: StateName
  count_runs: number
  sum_estimated_run_time: number
  sum_estimated_lateness: number
}

export default class FlowRunStateHistory implements IFlowRunStateHistory {
  public readonly state_type: StateType
  public readonly state_name: StateName
  public readonly count_runs: number
  public readonly sum_estimated_run_time: number
  public readonly sum_estimated_lateness: number

  constructor(state: IFlowRunStateHistory) {
    this.state_type = state.state_type
    this.state_name = state.state_name
    this.count_runs = state.count_runs
    this.sum_estimated_run_time = state.sum_estimated_run_time
    this.sum_estimated_lateness = state.sum_estimated_lateness
  }
}
