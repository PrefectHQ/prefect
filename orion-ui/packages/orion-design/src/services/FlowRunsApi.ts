import { Route } from '.'
import { Api } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'

export type IFlowRunResponse = {
  name: 'string',
  expected_start_time: 'string',
}

export class FlowRunsApi extends Api {

  protected route: Route = '/flow_runs'

  public getFlowRun(id: string): Promise<IFlowRunResponse> {
    return this.get<IFlowRunResponse>(`/${id}`).then(response => response.data)
  }

  public filter(filter: UnionFilters): Promise<IFlowRunResponse[]> {
    return this.post<IFlowRunResponse[]>('/filter', filter).then(response => response.data)
  }

  public getFlowRunsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

}

export const flowRunsApi = new FlowRunsApi()