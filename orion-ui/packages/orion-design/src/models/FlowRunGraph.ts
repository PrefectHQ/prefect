import { IState } from '@/models/State'

export interface IFlowRunGraph {
  id: string,
  upstreamDependencies: {
    inputType: 'constant' | 'parameter' | 'task_run',
    id: string,
  }[],
  state: IState | null,
}

export class FlowRunGraph implements IFlowRunGraph {
  public readonly id: string
  public upstreamDependencies: { inputType: 'constant' | 'parameter' | 'task_run', id: string }[]
  public state: IState | null

  public constructor(flowRunGraph: FlowRunGraph) {
    this.id = flowRunGraph.id
    this.upstreamDependencies = flowRunGraph.upstreamDependencies
    this.state = flowRunGraph.state
  }
}
