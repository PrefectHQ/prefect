import { InjectionKey } from 'vue'
import { ITaskRunResponse } from '@/models/ITaskRunResponse'
import { TaskRun } from '@/models/TaskRun'
import { Api, ApiRoute } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'
import { mapper } from '@/services/Mapper'

export class TaskRunsApi extends Api {

  protected route: ApiRoute = '/task_runs'

  public getTaskRun(id: string): Promise<TaskRun> {
    return this.get<ITaskRunResponse>(`/${id}`)
      .then(({ data }) => mapper.map('ITaskRunResponse', data, 'TaskRun'))
  }

  public getTaskRuns(filter: UnionFilters): Promise<TaskRun[]> {
    return this.post<ITaskRunResponse[]>('/filter', filter)
      .then(({ data }) => mapper.map('ITaskRunResponse', data, 'TaskRun'))
  }

  public getTaskRunsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

}

export const taskRunsApiKey: InjectionKey<TaskRunsApi> = Symbol('taskRunsApiKey')