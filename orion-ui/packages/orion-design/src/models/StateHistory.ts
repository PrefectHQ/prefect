import { State } from '@/types/states'

export type IStateHistory = {
  stateType: State,
  stateName: string,
  countRuns: number,
  sumEstimatedRunTime: number,
  sumEstimatedLateness: number,
}

export class StateHistory implements IStateHistory {
  public readonly stateType: State
  public readonly stateName: string
  public readonly countRuns: number
  public readonly sumEstimatedRunTime: number
  public readonly sumEstimatedLateness: number

  public constructor(state: IStateHistory) {
    this.stateType = state.stateType
    this.stateName = state.stateName
    this.countRuns = state.countRuns
    this.sumEstimatedRunTime = state.sumEstimatedRunTime
    this.sumEstimatedLateness = state.sumEstimatedLateness
  }
}