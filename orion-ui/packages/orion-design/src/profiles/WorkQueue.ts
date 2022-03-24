import { IWorkQueueResponse } from '@/models/IWorkQueueResponse'
import { WorkQueue } from '@/models/WorkQueue'
import { Profile, translate } from '@/services/Translate'

export const workQueueProfile: Profile<IWorkQueueResponse, WorkQueue> = {
  toDestination(source) {
    return new WorkQueue({
      id: source.id,
      created: new Date(source.created),
      updated: new Date(source.updated),
      name: source.name,
      filter: (this as typeof translate).toDestination('IWorkQueueFilterResponse:WorkQueueFilter', source.filter),
      description: source.description,
      isPaused: source.is_paused ?? false,
      concurrencyLimit: source.concurrency_limit,
    })
  },
  toSource(destination) {
    return {
      'id': destination.id,
      'created': destination.created.toISOString(),
      'updated': destination.updated.toISOString(),
      'name': destination.name,
      'filter': (this as typeof translate).toSource('IWorkQueueFilterResponse:WorkQueueFilter', destination.filter),
      'description': destination.description,
      'is_paused': destination.isPaused,
      'concurrency_limit': destination.concurrencyLimit,
    }
  },
}