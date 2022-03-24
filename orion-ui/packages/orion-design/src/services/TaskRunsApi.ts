import { createActions } from '@prefecthq/vue-compositions'
import { InjectionKey } from 'vue'
import { ITaskRunResponse } from '@/models/ITaskRunResponse'
import { TaskRun } from '@/models/TaskRun'
import { Api, Route } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'
import { translate } from '@/services/Translate'

export class TaskRunsApi extends Api {

  protected route: Route = '/task_runs'

  public getTaskRun(id: string): Promise<TaskRun> {
    return this.get<ITaskRunResponse>(`/${id}`)
      .then(({ data }) => translate.toDestination('ITaskRunResponse:TaskRun', data))
  }

  public getTaskRuns(filter: UnionFilters): Promise<TaskRun[]> {
    return this.post<ITaskRunResponse[]>('/filter', filter)
      .then(({ data }) => data.map(x => translate.toDestination('ITaskRunResponse:TaskRun', x)))
  }

  public getTaskRunsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

}

export const taskRunsApi = createActions(new TaskRunsApi())

export const getTaskRunKey: InjectionKey<TaskRunsApi['getTaskRun']> = Symbol()