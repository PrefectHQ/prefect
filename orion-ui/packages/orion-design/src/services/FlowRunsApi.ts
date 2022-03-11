import { createActions } from '@prefecthq/vue-compositions'
import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import { FlowRun } from '@/models/FlowRun'
import { FlowRunGraph } from '@/models/FlowRunGraph'
import { IFlowRunGraphResponse } from '@/models/IFlowRunGraphResponse'
import { IFlowRunnerResponse } from '@/models/IFlowRunnerResponse'
import { RunHistory } from '@/models/RunHistory'
import { StateHistory } from '@/models/StateHistory'
import { StateType } from '@/models/StateType'
import { Api, Route } from '@/services/Api'
import { FlowRunsHistoryFilter, UnionFilters } from '@/services/Filter'
import { IStateResponse, statesApi } from '@/services/StatesApi'
import { DateString } from '@/types/dates'
import { State, StateName } from '@/types/states'

export type IFlowRunResponse = {
  id: string,
  created: DateString,
  updated: DateString,
  name: string | null,
  flow_id: string,
  state_id: string | null,
  deployment_id: string | null,
  flow_version: string | null,
  parameters: unknown,
  idempotency_key: string | null,
  context: unknown,
  empirical_policy: unknown,
  empirical_config: unknown,
  tags: string[] | null,
  parent_task_run_id: string | null,
  state_type: StateType | null,
  run_count: number | null,
  expected_start_time: DateString | null,
  next_scheduled_start_time: DateString | null,
  start_time: DateString | null,
  end_time: DateString | null,
  total_run_time: number | null,
  estimated_run_time: number | null,
  estimated_start_time_delta: number | null,
  auto_scheduled: boolean | null,
  flow_runner: IFlowRunnerResponse | null,
  state: IStateResponse | null,
}

export type IStateHistoryResponse = {
  state_type: State,
  state_name: StateName,
  count_runs: number,
  sum_estimated_run_time: number,
  sum_estimated_lateness: number,
}

export type IFlowRunHistoryResponse = {
  interval_start: Date,
  interval_end: Date,
  states: IStateHistoryResponse[],
}

export class FlowRunsApi extends Api {

  protected route: Route = '/flow_runs'

  public getFlowRun(id: string): Promise<FlowRun> {
    return this.get<IFlowRunResponse>(`/${id}`).then(response => this.mapFlowRunResponse(response))
  }

  public getFlowRuns(filter: UnionFilters): Promise<FlowRun[]> {
    return this.post<IFlowRunResponse[]>('/filter', filter).then(response => this.mapFlowRunsResponse(response))
  }

  public getFlowRunsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  public getFlowRunsHistory(filter: FlowRunsHistoryFilter): Promise<RunHistory[]> {
    return this.post<IFlowRunHistoryResponse[]>('/history', filter).then(response => this.mapFlowRunsHistoryResponse(response))
  }

  public getFlowRunsGraph(id: string): Promise<FlowRunGraph[]> {
    return this.get<IFlowRunGraphResponse[]>(`/${id}/graph`).then(response => this.mapFlowRunGraphResponse(response))
  }

  protected mapFlowRun(data: IFlowRunResponse): FlowRun {
    return new FlowRun({
      id: data.id,
      deploymentId: data.deployment_id,
      flowId: data.flow_id,
      flowVersion: data.flow_version,
      idempotencyKey: data.idempotency_key,
      expectedStartTime: data.expected_start_time,
      nextScheduledStartTime: data.next_scheduled_start_time,
      parameters: data.parameters,
      autoScheduled: data.auto_scheduled,
      context: data.context,
      empiricalConfig: data.empirical_config,
      empiricalPolicy: data.empirical_policy,
      estimatedRunTime: data.estimated_run_time,
      estimatedStartTimeDelta: data.estimated_start_time_delta,
      totalRunTime: data.total_run_time,
      startTime: data.start_time ? new Date(data.start_time) : null,
      endTime: data.end_time ? new Date(data.end_time) : null,
      name: data.name,
      parentTaskRunId: data.parent_task_run_id,
      stateId: data.state_id,
      stateType: data.state_type,
      state: data.state ? statesApi.mapStateResponse(data.state) : null,
      tags: data.tags,
      runCount: data.run_count,
      created: new Date(data.created),
      updated: new Date(data.updated),
    })
  }

  protected mapFlowRunsHistory(data: IFlowRunHistoryResponse): RunHistory {
    return new RunHistory({
      intervalStart: new Date(data.interval_start),
      intervalEnd: new Date(data.interval_end),
      states: data.states.map(x => this.mapStateHistory(x)),
    })
  }

  protected mapStateHistory(data: IStateHistoryResponse): StateHistory {
    return new StateHistory({
      stateType: data.state_type,
      stateName: data.state_name,
      countRuns: data.count_runs,
      sumEstimatedRunTime: data.sum_estimated_run_time,
      sumEstimatedLateness: data.sum_estimated_lateness,
    })
  }

  protected mapFlowRunGraphResponse({ data }: AxiosResponse<IFlowRunGraphResponse[]>): FlowRunGraph[] {
    return data.map((x: IFlowRunGraphResponse) => new FlowRunGraph({
      id: x.id,
      expectedStartTime: x.expected_start_time,
      startTime: x.start_time ? new Date(x.start_time) : null,
      endTime: x.end_time ? new Date(x.end_time) : null,
      totalRunTime: x.total_run_time,
      estimatedRunTime: x.estimated_run_time,
      upstreamDependencies: this.mapFlowRunGraphDependenciesResponse(x.upstream_dependencies),
      state: statesApi.mapStateResponse(x.state),
    }))
  }

  protected mapFlowRunGraphDependenciesResponse(data: IFlowRunGraphResponse['upstream_dependencies']): FlowRunGraph['upstreamDependencies'] {
    return data.map(x => {
      return {
        id: x.id,
        inputType: x.input_type,
      }
    })
  }

  protected mapFlowRunsHistoryResponse({ data }: AxiosResponse<IFlowRunHistoryResponse[]>): RunHistory[] {
    return data.map(x => this.mapFlowRunsHistory(x))
  }

  protected mapFlowRunHistoryResponse({ data }: AxiosResponse<IFlowRunHistoryResponse>): RunHistory {
    return this.mapFlowRunsHistory(data)
  }

  protected mapFlowRunsResponse({ data }: AxiosResponse<IFlowRunResponse[]>): FlowRun[] {
    return data.map(x => this.mapFlowRun(x))
  }

  protected mapFlowRunResponse({ data }: AxiosResponse<IFlowRunResponse>): FlowRun {
    return this.mapFlowRun(data)
  }

}

export const flowRunsApi = createActions(new FlowRunsApi())

export const getFlowRunsCountKey: InjectionKey<FlowRunsApi['getFlowRunsCount']> = Symbol()