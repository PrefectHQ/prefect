import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import { PaginatedFilter } from '.'
import { IWorkQueueFilterResponse } from '@/models/IWorkQueueFilterResponse'
import { IWorkQueueRequest } from '@/models/IWorkQueueRequest'
import { IWorkQueueResponse } from '@/models/IWorkQueueResponse'
import { WorkQueue } from '@/models/WorkQueue'
import { WorkQueueFilter } from '@/models/WorkQueueFilter'
import { Api, ApiRoute } from '@/services/Api'

export class WorkQueuesApi extends Api {

  protected route: ApiRoute = '/work_queues'

  public getWorkQueue(id: string): Promise<WorkQueue> {
    return this.get<IWorkQueueResponse>(`/${id}`).then(response => this.mapWorkQueueResponse(response))
  }

  public getWorkQueues(filter: PaginatedFilter): Promise<WorkQueue[]> {
    return this.post<IWorkQueueResponse[]>('/filter', filter).then(response => this.mapWorkQueuesResponse(response))
  }

  public createWorkQueue(request: IWorkQueueRequest): Promise<WorkQueue> {
    return this.post<IWorkQueueResponse>('/', request).then(response => this.mapWorkQueueResponse(response))
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

  protected mapWorkQueue(data: IWorkQueueResponse): WorkQueue {
    return new WorkQueue({
      id: data.id,
      created: new Date(data.created),
      updated: new Date(data.updated),
      name: data.name,
      filter: this.mapWorkQueueFilter(data.filter),
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
      tags: data.tags ?? [],
      deploymentIds: data.deployment_ids ?? [],
      flowRunnerTypes: data.flow_runner_types ?? [],
    })
  }

}

export const workQueuesApiKey: InjectionKey<WorkQueuesApi> = Symbol('workQueuesApiKey')