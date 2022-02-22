import { AxiosResponse } from 'axios'
import { Route } from '.'
import { RunHistory } from '@/models/RunHistory'
import { StateHistory } from '@/models/StateHistory'
import { Api } from '@/services/Api'
import { FlowRunsHistoryFilter, UnionFilters } from '@/services/Filter'
import { State, StateName } from '@/types/states'

export type IFlowRunResponse = {
  name: 'string',
  expected_start_time: 'string',
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

  public getFlowRun(id: string): Promise<IFlowRunResponse> {
    return this.get<IFlowRunResponse>(`/${id}`).then(response => response.data)
  }

  public getFlowRuns(filter: UnionFilters): Promise<IFlowRunResponse[]> {
    return this.post<IFlowRunResponse[]>('/filter', filter).then(response => response.data)
  }

  public getFlowRunsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  public getFlowRunsHistory(filter: FlowRunsHistoryFilter): Promise<RunHistory[]> {
    return this.post<IFlowRunHistoryResponse[]>('/history', filter).then(response => this.mapFlowRunsHistoryResponse(response))
  }

  protected mapFlowRunsHistoryResponse({ data }: AxiosResponse<IFlowRunHistoryResponse[]>): RunHistory[] {
    return data.map(this.mapFlowRunsHistory)
  }

  protected mapFlowRunsHistory(flowRun: IFlowRunHistoryResponse): RunHistory {
    return new RunHistory({
      intervalStart: new Date(flowRun.interval_start),
      intervalEnd: new Date(flowRun.interval_end),
      states: flowRun.states.map(this.mapStateHistory),
    })
  }

  protected mapStateHistory(state: IStateHistoryResponse): StateHistory {
    return new StateHistory({
      stateType: state.state_type,
      stateName: state.state_name,
      countRuns: state.count_runs,
      sumEstimatedRunTime: state.sum_estimated_run_time,
      sumEstimatedLateness: state.sum_estimated_lateness,
    })
  }

}

export const flowRunsApi = new FlowRunsApi()