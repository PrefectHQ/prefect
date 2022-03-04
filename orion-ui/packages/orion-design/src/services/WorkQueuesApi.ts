import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import { PaginatedFilter } from '.'
import { WorkQueue } from '@/models/WorkQueue'
import { WorkQueueFilter } from '@/models/WorkQueueFilter'
import { Api, Route } from '@/services/Api'
import { DateString } from '@/types/dates'

export type IWorkQueueResponse = {
  id: string,
  created: DateString,
  updated: DateString,
  name: string,
  filter: IWorkQueueFilterResponse | null,
  description: string | null,
  is_paused: boolean | null,
  concurrency_limit: number | null,
}

export type IWorkQueueRequest = {
  name: string,
  filter: IWorkQueueFilterResponse | null,
  description: string | null,
  is_paused: boolean | null,
  concurrency_limit: number | null,
}

export type IWorkQueueFilterResponse = {
  tags: string[] | null,
  deployment_ids: string[] | null,
  flow_runner_types: string[] | null,
}

export class WorkQueuesApi extends Api {

  protected route: Route = '/work_queues'

  public getWorkQueue(id: string): Promise<WorkQueue> {
    return this.get<IWorkQueueResponse>(`/${id}`).then(response => this.mapWorkQueueResponse(response))
  }

  public getWorkQueues(filter: PaginatedFilter): Promise<WorkQueue[]> {
    return this.post<IWorkQueueResponse[]>('/filter', filter).then(response => this.mapWorkQueuesResponse(response))
  }

  public createWorkQueue(request: IWorkQueueRequest): Promise<WorkQueue> {
    return this.post<IWorkQueueResponse>('/', request).then(response => this.mapWorkQueueResponse(response))
  }

  public updateWorkQueue(id: string, request: IWorkQueueRequest): Promise<void> {
    return this.patch(`/${id}`, request)
  }

  public deleteWorkQueue(id: string): Promise<void> {
    return this.delete(`/${id}`)
  }

  protected mapWorkQueue(data: IWorkQueueResponse): WorkQueue {
    return new WorkQueue({
      id: data.id,
      created: new Date(data.created),
      updated: new Date(data.updated),
      name: data.name,
      filter: data.filter ? this.mapWorkQueueFilter(data.filter) : null,
      description: data.description,
      isPaused: data.is_paused ?? false,
      concurrencyLimit: data.concurrency_limit,
    })
  }

  protected mapWorkQueueResponse({ data }: AxiosResponse<IWorkQueueResponse>): WorkQueue {
    return this.mapWorkQueue(data)
  }

  protected mapWorkQueuesResponse({ data }: AxiosResponse<IWorkQueueResponse[]>): WorkQueue[] {
    return data.map(x => this.mapWorkQueue(x))
  }

  protected mapWorkQueueFilter(data: IWorkQueueFilterResponse): WorkQueueFilter {
    return new WorkQueueFilter({
      tags: data.tags,
      deploymentIds: data.deployment_ids,
      flowRunnerTypes: data.flow_runner_types,
    })
  }

}

export const getWorkQueuesKey: InjectionKey<WorkQueuesApi['getWorkQueues']> = Symbol()

export const workQueuesApi = new WorkQueuesApi()