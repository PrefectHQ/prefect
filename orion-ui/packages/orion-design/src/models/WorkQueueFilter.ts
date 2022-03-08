import { FlowRunnerType } from '@/types/FlowRunnerType'

export interface IWorkQueueFilter {
  tags: string[],
  deploymentIds: string[],
  flowRunnerTypes: FlowRunnerType[],
}

export class WorkQueueFilter implements IWorkQueueFilter {
  public tags: string[]
  public deploymentIds: string[]
  public flowRunnerTypes: FlowRunnerType[]

  public constructor(filter: IWorkQueueFilter) {
    this.tags = filter.tags
    this.deploymentIds = filter.deploymentIds
    this.flowRunnerTypes = filter.flowRunnerTypes
  }
}