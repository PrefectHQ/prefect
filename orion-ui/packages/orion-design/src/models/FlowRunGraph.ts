import { IState } from '@/models/State'

export type TaskRunInputType = 'constant' | 'parameter' | 'task_run'

export interface IFlowRunGraph {
  id: string,
  upstreamDependencies: {
    inputType: TaskRunInputType,
    id: string,
  }[],
  state: IState | null,
}

export class FlowRunGraph implements IFlowRunGraph {
  public readonly id: string
  public upstreamDependencies: { inputType: TaskRunInputType, id: string }[]
  public state: IState | null

  public constructor(flowRunGraph: FlowRunGraph) {
    this.id = flowRunGraph.id
    this.upstreamDependencies = flowRunGraph.upstreamDependencies
    this.state = flowRunGraph.state
  }
}
