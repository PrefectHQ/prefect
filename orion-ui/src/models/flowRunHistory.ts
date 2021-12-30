import FlowRunStateHistory, {
  IFlowRunStateHistory
} from './flowRunStateHistory'

export type IFlowRunHistory = {
  interval_start: Date
  interval_end: Date
  states: IFlowRunStateHistory[]
}

export default class FlowRunHistory implements IFlowRunHistory {
  public readonly interval_start: Date
  public readonly interval_end: Date
  public readonly states: FlowRunStateHistory[]

  constructor(flow: IFlowRunHistory) {
    this.interval_start = flow.interval_start
    this.interval_end = flow.interval_end
    this.states = flow.states.map((state) => new FlowRunStateHistory(state))
  }
}
