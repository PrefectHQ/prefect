import { IWorkQueueResponse } from '@/models/IWorkQueueResponse'
import { WorkQueue } from '@/models/WorkQueue'
import { MapFunction } from '@/services/Mapper'

export const mapIWorkQueueResponseToWorkQueue: MapFunction<IWorkQueueResponse, WorkQueue> = function(source: IWorkQueueResponse): WorkQueue {
  return new WorkQueue({
    id: source.id,
    created: this.map('string', source.created, 'Date'),
    updated: this.map('string', source.updated, 'Date'),
    name: source.name,
    filter: this.map('IWorkQueueFilterResponse', source.filter, 'WorkQueueFilter'),
    description: source.description,
    isPaused: source.is_paused ?? false,
    concurrencyLimit: source.concurrency_limit,
  })
}

export const mapWorkQueueToIWorkQueueResponse: MapFunction<WorkQueue, IWorkQueueResponse> = function(source: WorkQueue): IWorkQueueResponse {
  return {
    'id': source.id,
    'created': this.map('Date', source.created, 'string'),
    'updated': this.map('Date', source.updated, 'string'),
    'name': source.name,
    'filter': this.map('WorkQueueFilter', source.filter, 'IWorkQueueFilterResponse'),
    'description': source.description,
    'is_paused': source.isPaused,
    'concurrency_limit': source.concurrencyLimit,
  }
}