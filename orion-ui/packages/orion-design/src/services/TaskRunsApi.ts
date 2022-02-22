import { AxiosResponse } from 'axios'
import { Route, UnionFilters } from '.'
import { EmpiricalPolicy } from '@/models/EmpiricalPolicy'
import { IEmpiricalPolicyResponse } from '@/models/IEmpiricalPolicyResponse'
import { ITaskInputResponse } from '@/models/ITaskInputResponse'
import { StateType } from '@/models/StateType'
import { TaskInput } from '@/models/TaskInput'
import { TaskRun } from '@/models/TaskRun'
import { Api } from '@/services/Api'
import { IStateResponse, statesApi } from '@/services/StatesApi'
import { DateString } from '@/types/dates'

export type ITaskRunResponse = {
  id: string,
  created: string,
  updated: string,
  name: string | null,
  flow_run_id: string,
  task_key: string,
  dynamic_key: string,
  cache_key: string | null,
  cache_expiration: DateString | null,
  task_version: string | null,
  empirical_policy: IEmpiricalPolicyResponse | null,
  tags: string[] | null,
  state_id: string | null,
  task_inputs: Record<string, ITaskInputResponse[]> | null,
  state_type: StateType | null,
  run_count: number | null,
  expected_start_time: DateString | null,
  next_scheduled_start_time: DateString | null,
  start_time: DateString | null,
  end_time: DateString | null,
  total_run_time: number | null,
  estimated_run_time: number | null,
  estimated_start_time_delta: number | null,
  state: IStateResponse | null,
}

export class TaskRunsApi extends Api {

  protected route: Route = '/task_runs'

  public getTaskRun(id: string): Promise<TaskRun> {
    return this.get<ITaskRunResponse>(`/${id}`).then(response => this.mapTaskRunResponse(response))
  }

  public getTaskRuns(filter: UnionFilters): Promise<TaskRun[]> {
    return this.post<ITaskRunResponse[]>('/filter', filter).then(response => this.mapTaskRunsResponse(response))
  }

  public getTaskRunsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  protected mapEmpiricalPolicy(data: IEmpiricalPolicyResponse): EmpiricalPolicy {
    return new EmpiricalPolicy({
      maxRetries: data.max_retries,
      retryDelaySeconds: data.retry_delay_seconds,
    })
  }

  protected mapTaskInputs(data: Record<string, ITaskInputResponse[]>): Record<string, TaskInput[]> {
    const response = {} as Record<string, TaskInput[]>

    return Object.entries(data).reduce<Record<string, TaskInput[]>>((mapped, [key, value]) => {
      mapped[key] = value.map(this.mapTaskInput)

      return mapped
    }, response)
  }

  protected mapTaskInput(data: ITaskInputResponse): TaskInput {
    return new TaskInput({
      inputType: data.input_type,
      name: data.name,
    })
  }

  protected mapTaskRun(data: ITaskRunResponse): TaskRun {
    return new TaskRun({
      id: data.id,
      flowRunId: data.flow_run_id,
      cacheExpiration: data.cache_expiration,
      cacheKey: data.cache_key,
      created: new Date(data.created),
      dynamicKey: data.dynamic_key,
      empiricalPolicy: data.empirical_policy ? this.mapEmpiricalPolicy(data.empirical_policy) : null,
      estimatedRunTime: data.estimated_run_time,
      estimatedStartTimeDelta: data.estimated_start_time_delta,
      totalRunTime: data.total_run_time,
      expectedStartTime: data.expected_start_time ? new Date(data.expected_start_time) : null,
      nextScheduledStartTime: data.next_scheduled_start_time,
      runCount: data.run_count,
      name: data.name,
      taskInputs: data.task_inputs ? this.mapTaskInputs(data.task_inputs) : null,
      taskKey: data.task_key,
      taskVersion: data.task_version,
      updated: new Date(data.updated),
      startTime: data.start_time ? new Date(data.start_time) : null,
      endTime: data.end_time ? new Date(data.end_time) : null,
      stateId: data.state_id,
      stateType: data.state_type,
      state: data.state ? statesApi.stateMapper(data.state) : null,
      tags: data.tags,
    })
  }

  protected mapTaskRunResponse({ data }: AxiosResponse<ITaskRunResponse>): TaskRun {
    return this.mapTaskRun(data)
  }

  protected mapTaskRunsResponse({ data }: AxiosResponse<ITaskRunResponse[]>): TaskRun[] {
    return data.map(this.mapTaskRun)
  }

}

export const taskRunsApi = new TaskRunsApi()