import { IWorkQueueFilter } from '@/models/WorkQueueFilter'

export interface IWorkQueue {
  readonly id: string,
  created: Date,
  updated: Date,
  name: string,
  filter: IWorkQueueFilter,
  description: string | null,
  isPaused: boolean,
  concurrencyLimit: number | null,
}

export class WorkQueue implements IWorkQueue {
  public readonly id: string
  public created: Date
  public updated: Date
  public name: string
  public filter: IWorkQueueFilter
  public description: string | null
  public isPaused: boolean
  public concurrencyLimit: number | null

  public constructor(workQueue: IWorkQueue) {
    this.id = workQueue.id
    this.created = workQueue.created
    this.updated = workQueue.updated
    this.name = workQueue.name
    this.filter = workQueue.filter
    this.description = workQueue.description
    this.isPaused = workQueue.isPaused
    this.concurrencyLimit = workQueue.concurrencyLimit
  }
}