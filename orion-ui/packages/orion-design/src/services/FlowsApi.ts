import { createActions } from '@prefecthq/vue-compositions'
import { InjectionKey } from 'vue'
import { Flow } from '@/models/Flow'
import { IFlowResponse } from '@/models/IFlowResponse'
import { Api, Route } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'
import { mapper } from '@/services/Mapper'

export class FlowsApi extends Api {

  protected route: Route = '/flows'

  public getFlow(id: string): Promise<Flow> {
    return this.get<IFlowResponse>(`/${id}`)
      .then(({ data }) => mapper.map('IFlowResponse', data, 'Flow'))
  }

  public getFlows(filter: UnionFilters): Promise<Flow[]> {
    return this.post<IFlowResponse[]>('/filter', filter)
      .then(({ data }) => mapper.map('IFlowResponse', data, 'Flow'))
  }

  public getFlowsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

}

export const flowsApi = createActions(new FlowsApi())

export const getFlowsKey: InjectionKey<FlowsApi['getFlows']> = Symbol()