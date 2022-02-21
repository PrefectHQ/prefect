import { Api, Route } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'

export class FlowsApi extends Api {

  protected route: Route = '/flows'

  public getFlowsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

}

export const flowsApi = new FlowsApi()