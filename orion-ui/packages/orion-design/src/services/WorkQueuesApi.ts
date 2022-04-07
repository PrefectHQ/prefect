import { createActions } from '@prefecthq/vue-compositions'
import { InjectionKey } from 'vue'
import { IWorkQueueRequest } from '@/models/IWorkQueueRequest'
import { IWorkQueueResponse } from '@/models/IWorkQueueResponse'
import { WorkQueue } from '@/models/WorkQueue'
import { Api, Route } from '@/services/Api'
import { PaginatedFilter } from '@/services/Filter'
import { mapper } from '@/services/Mapper'

export class WorkQueuesApi extends Api {

  protected route: Route = '/work_queues'

  public getWorkQueue(id: string): Promise<WorkQueue> {
    return this.get<IWorkQueueResponse>(`/${id}`)
      .then(({ data }) => mapper.map('IWorkQueueResponse', data, 'WorkQueue'))
  }

  public getWorkQueues(filter: PaginatedFilter): Promise<WorkQueue[]> {
    return this.post<IWorkQueueResponse[]>('/filter', filter)
      .then(({ data }) => mapper.map('IWorkQueueResponse', data, 'WorkQueue'))
  }

  public createWorkQueue(request: IWorkQueueRequest): Promise<WorkQueue> {
    return this.post<IWorkQueueResponse>('/', request)
      .then(({ data }) => mapper.map('IWorkQueueResponse', data, 'WorkQueue'))
  }

  public pauseWorkQueue(id: string): Promise<void> {
    return this.patch(`/${id}`, { 'is_paused': true })
  }

  public resumeWorkQueue(id: string): Promise<void> {
    return this.patch(`/${id}`, { 'is_paused': false })
  }

  public updateWorkQueue(id: string, request: IWorkQueueRequest): Promise<void> {
    return this.patch(`/${id}`, request)
  }

  public deleteWorkQueue(id: string): Promise<void> {
    return this.delete(`/${id}`)
  }

}

export const getWorkQueueKey: InjectionKey<WorkQueuesApi['getWorkQueue']> = Symbol()
export const pauseWorkQueueKey: InjectionKey<WorkQueuesApi['pauseWorkQueue']> = Symbol()
export const resumeWorkQueueKey: InjectionKey<WorkQueuesApi['resumeWorkQueue']> = Symbol()
export const createWorkQueueKey: InjectionKey<WorkQueuesApi['createWorkQueue']> = Symbol()
export const updateWorkQueueKey: InjectionKey<WorkQueuesApi['updateWorkQueue']> = Symbol()
export const deleteWorkQueueKey: InjectionKey<WorkQueuesApi['deleteWorkQueue']> = Symbol()

export const workQueuesApi = createActions(new WorkQueuesApi())