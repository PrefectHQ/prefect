import { createActions } from '@prefecthq/vue-compositions'
import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import { FlowRun } from '@/models/FlowRun'
import { FlowRunGraph } from '@/models/FlowRunGraph'
import { IFlowRunGraphResponse } from '@/models/IFlowRunGraphResponse'
import { IFlowRunHistoryResponse } from '@/models/IFlowRunHistoryResponse'
import { IFlowRunResponse } from '@/models/IFlowRunResponse'
import { RunHistory } from '@/models/RunHistory'
import { Api, Route } from '@/services/Api'
import { FlowRunsHistoryFilter, UnionFilters } from '@/services/Filter'
import { translate } from '@/services/Translate'

export class FlowRunsApi extends Api {

  protected route: Route = '/flow_runs'

  public getFlowRun(id: string): Promise<FlowRun> {
    return this.get<IFlowRunResponse>(`/${id}`)
      .then(({ data }) => translate.toDestination('IFlowRunResponse:FlowRun', data))
  }

  public getFlowRuns(filter: UnionFilters): Promise<FlowRun[]> {
    return this.post<IFlowRunResponse[]>('/filter', filter)
      .then(({ data }) => data.map(x => translate.toDestination('IFlowRunResponse:FlowRun', x)))
  }

  public getFlowRunsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  public getFlowRunsHistory(filter: FlowRunsHistoryFilter): Promise<RunHistory[]> {
    return this.post<IFlowRunHistoryResponse[]>('/history', filter)
      .then(({ data }) => data.map(x => translate.toDestination('IFlowRunHistoryResponse:RunHistory', x)))
  }

  public getFlowRunsGraph(id: string): Promise<FlowRunGraph[]> {
    return this.get<IFlowRunGraphResponse[]>(`/${id}/graph`)
      .then(({ data }) => data.map(x => translate.toDestination('IFlowRunGraphResponse:FlowRunGraph', x)))
  }
}

export const flowRunsApi = createActions(new FlowRunsApi())

export const getFlowRunsCountKey: InjectionKey<FlowRunsApi['getFlowRunsCount']> = Symbol()