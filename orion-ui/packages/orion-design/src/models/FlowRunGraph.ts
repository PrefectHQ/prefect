import { IState } from '@/models/State'

export type TaskRunInputType = 'constant' | 'parameter' | 'task_run'

export interface IFlowRunGraph {
  id: string,
  upstreamDependencies: {
    inputType: TaskRunInputType,
    id: string,
  }[],
  state: IState | null,
  expectedStartTime: Date | null,
  estimatedRunTime: number | null,
  totalRunTime: number | null,
  startTime: Date | null,
  endTime: Date | null,
}

export class FlowRunGraph implements IFlowRunGraph {
  public readonly id: string
  public upstreamDependencies: { inputType: TaskRunInputType, id: string }[]
  public state: IState | null
  public expectedStartTime: Date | null
  public estimatedRunTime: number | null
  public totalRunTime: number | null
  public startTime: Date | null
  public endTime: Date | null

  public constructor(flowRunGraph: FlowRunGraph) {
    this.id = flowRunGraph.id
    this.upstreamDependencies = flowRunGraph.upstreamDependencies
    this.state = flowRunGraph.state
    this.expectedStartTime = flowRunGraph.expectedStartTime
    this.estimatedRunTime = flowRunGraph.estimatedRunTime
    this.totalRunTime = flowRunGraph.totalRunTime
    this.startTime = flowRunGraph.startTime
    this.endTime = flowRunGraph.endTime
  }
}
