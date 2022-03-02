export interface IWorkQueueFilter {
  tags: string[] | null,
  deploymentIds: string[] | null,
  flowRunnerTypes: string[] | null,
}

export class WorkQueueFilter implements IWorkQueueFilter {
  public tags: string[] | null
  public deploymentIds: string[] | null
  public flowRunnerTypes: string[] | null

  public constructor(filter: IWorkQueueFilter) {
    this.tags = filter.tags
    this.deploymentIds = filter.deploymentIds
    this.flowRunnerTypes = filter.flowRunnerTypes
  }
}