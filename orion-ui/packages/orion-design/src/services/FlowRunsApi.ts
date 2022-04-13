import { InjectionKey } from 'vue'
import { FlowRun } from '@/models/FlowRun'
import { FlowRunGraph } from '@/models/FlowRunGraph'
import { IFlowRunGraphResponse } from '@/models/IFlowRunGraphResponse'
import { IFlowRunHistoryResponse } from '@/models/IFlowRunHistoryResponse'
import { IFlowRunResponse } from '@/models/IFlowRunResponse'
import { RunHistory } from '@/models/RunHistory'
import { Api, ApiRoute } from '@/services/Api'
import { FlowRunsHistoryFilter, UnionFilters } from '@/services/Filter'
import { mapper } from '@/services/Mapper'

export class FlowRunsApi extends Api {

  protected route: ApiRoute = '/flow_runs'

  public getFlowRun(id: string): Promise<FlowRun> {
    return this.get<IFlowRunResponse>(`/${id}`)
      .then(({ data }) => mapper.map('IFlowRunResponse', data, 'FlowRun'))
  }

  public getFlowRuns(filter: UnionFilters): Promise<FlowRun[]> {
    return this.post<IFlowRunResponse[]>('/filter', filter)
      .then(({ data }) => mapper.map('IFlowRunResponse', data, 'FlowRun'))
  }

  public getFlowRunsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  public getFlowRunsHistory(filter: FlowRunsHistoryFilter): Promise<RunHistory[]> {
    return this.post<IFlowRunHistoryResponse[]>('/history', filter)
      .then(({ data }) => mapper.map('IFlowRunHistoryResponse', data, 'RunHistory'))
  }

  public getFlowRunsGraph(id: string): Promise<FlowRunGraph[]> {
    return this.get<IFlowRunGraphResponse[]>(`/${id}/graph`)
      .then(({ data }) => mapper.map('IFlowRunGraphResponse', data, 'FlowRunGraph'))
  }
}

export const flowRunsApiKey: InjectionKey<FlowRunsApi> = Symbol('flowRunsApiKey')