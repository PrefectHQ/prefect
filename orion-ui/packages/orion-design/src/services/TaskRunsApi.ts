import { AxiosResponse } from 'axios'
import { TaskRun } from '../models/TaskRun'
import { StateType } from '../types/StateType'
import { Api } from './Api'
import { IStateResponse, States } from './StatesApi'

export type ITaskRunResponse = {
  id: string,
  flow_run_id: string,
  cache_expiration: string,
  cache_key: string,
  created: string,
  dynamic_key: string,
  empirical_policy: Record<string, unknown>,
  estimated_run_time: number,
  estimated_start_time_delta: number,
  total_run_time: number,
  expected_start_time: string,
  next_scheduled_start_time: string | null,
  run_count: number,
  name: string,
  task_inputs: Record<string, unknown>,
  task_key: string,
  task_version: string,
  updated: string,
  start_time: string,
  end_time: string,
  state_id: string,
  state_type: StateType,
  state: IStateResponse,
  duration: number,
  subflow_runs: boolean,
  tags: string[],
}

export class TaskRunsApi extends Api {

  protected route: string = '/api/task_runs'

  public getTaskRun(id: string): Promise<TaskRun> {
    return this.get(`/${id}`).then(response => this.taskRunResponseMapper(response))
  }

  protected taskRunMapper(taskRun: ITaskRunResponse): TaskRun {
    return new TaskRun({
      id: taskRun.id,
      flowRunId: taskRun.flow_run_id,
      cacheExpiration: taskRun.cache_expiration,
      cacheKey: taskRun.cache_key,
      created: new Date(taskRun.created),
      dynamicKey: taskRun.dynamic_key,
      empiricalPolicy: taskRun.empirical_policy,
      estimatedRunTime: taskRun.estimated_run_time,
      estimatedStartTimeDelta: taskRun.estimated_start_time_delta,
      totalRunTime: taskRun.total_run_time,
      expectedStartTime: new Date(taskRun.expected_start_time),
      nextScheduledStartTime: taskRun.next_scheduled_start_time,
      runCount: taskRun.run_count,
      name: taskRun.name,
      taskInputs: taskRun.task_inputs,
      taskKey: taskRun.task_key,
      taskVersion: taskRun.task_version,
      updated: new Date(taskRun.updated),
      startTime: new Date(taskRun.start_time),
      endTime: new Date(taskRun.end_time),
      stateId: taskRun.state_id,
      stateType: taskRun.state_type,
      state: States.stateMapper(taskRun.state),
      duration: taskRun.duration,
      subflowRuns: taskRun.subflow_runs,
      tags: taskRun.tags,
    })
  }

  protected taskRunResponseMapper({ data }: AxiosResponse<ITaskRunResponse>): TaskRun {
    return this.taskRunMapper(data)
  }

  protected taskRunsResponseMapper({ data }: AxiosResponse<ITaskRunResponse[]>): TaskRun[] {
    return data.map(task => this.taskRunMapper(task))
  }
}

export const TaskRuns = new TaskRunsApi()