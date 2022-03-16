import { IStateHistory, StateHistory } from '@/models/StateHistory'

export type IRunHistory = {
  intervalStart: Date,
  intervalEnd: Date,
  states: IStateHistory[],
}

export class RunHistory implements IRunHistory {
  public readonly intervalStart: Date
  public readonly intervalEnd: Date
  public readonly states: StateHistory[]

  public constructor(run: IRunHistory) {
    this.intervalStart = run.intervalStart
    this.intervalEnd = run.intervalEnd
    this.states = run.states.map((state) => new StateHistory(state))
  }
}