import { Api, Route } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'

export class DeploymentsApi extends Api {

  protected route: Route = '/deployments'

  public getDeploymentsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

}

export const deploymentsApi = new DeploymentsApi()