import { WorkQueue } from '@/models/WorkQueue'
import { FlowRunnerType } from '@/types/FlowRunnerType'

export class WorkQueueFormValues {
  public id: string | null
  public name: string | null
  public description: string | null
  public concurrencyLimit: number | null
  public filter: {
    tags: string[],
    flowRunnerTypes: FlowRunnerType[],
    deploymentIds: string[],
  }
  public isPaused: boolean

  public constructor(workQueue?: WorkQueue) {
    this.id = workQueue?.id ?? null
    this.name = workQueue?.name ?? null
    this.description = workQueue?.description ?? null
    this.concurrencyLimit = workQueue?.concurrencyLimit ?? null
    this.isPaused = workQueue?.isPaused ?? false
    this.filter = workQueue?.filter ?? {
      tags: [],
      flowRunnerTypes: [],
      deploymentIds: [],
    }
  }
}