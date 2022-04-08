import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import { EmpiricalPolicy } from '@/models/EmpiricalPolicy'
import { IEmpiricalPolicyResponse } from '@/models/IEmpiricalPolicyResponse'
import { isConstantTaskInputResponse, isParameterTaskInputResponse, isTaskRunTaskInputResponse, ITaskInputResponse } from '@/models/ITaskInputResponse'
import { ITaskRunResponse } from '@/models/ITaskRunResponse'
import { ConstantTaskInput, ParameterTaskInput, TaskInput, TaskRunTaskInput } from '@/models/TaskInput'
import { TaskRun } from '@/models/TaskRun'
import { Api, ApiRoute } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'
import { statesApi } from '@/services/StatesApi'

export class TaskRunsApi extends Api {

  protected route: ApiRoute = '/task_runs'

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
      mapped[key] = value.map(x => this.mapTaskInput(x))

      return mapped
    }, response)
  }

  protected mapTaskInput(data: ITaskInputResponse): TaskInput {
    if (isConstantTaskInputResponse(data)) {
      return new ConstantTaskInput({
        inputType: data.input_type,
        type: data.type,
      })
    }

    if (isParameterTaskInputResponse(data)) {
      return new ParameterTaskInput({
        inputType: data.input_type,
        name: data.name,
      })
    }

    if (isTaskRunTaskInputResponse(data)) {
      return new TaskRunTaskInput({
        inputType: data.input_type,
        id: data.id,
      })
    }

    throw 'Invalid ITaskInputResponse'
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
      state: data.state ? statesApi.mapStateResponse(data.state) : null,
      tags: data.tags,
    })
  }

  protected mapTaskRunResponse({ data }: AxiosResponse<ITaskRunResponse>): TaskRun {
    return this.mapTaskRun(data)
  }

  protected mapTaskRunsResponse({ data }: AxiosResponse<ITaskRunResponse[]>): TaskRun[] {
    return data.map(x => this.mapTaskRun(x))
  }

}

export const taskRunsApiKey: InjectionKey<TaskRunsApi> = Symbol('taskRunsApiKey')