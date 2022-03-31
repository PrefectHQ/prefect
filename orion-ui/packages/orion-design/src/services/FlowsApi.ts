import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import { Flow } from '@/models/Flow'
import { IFlowResponse } from '@/models/IFlowResponse'
import { Api, ApiRoute } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'

export class FlowsApi extends Api {

  protected route: ApiRoute = '/flows'

  public getFlow(id: string): Promise<Flow> {
    return this.get<IFlowResponse>(`/${id}`).then(response => this.mapFlowResponse(response))
  }

  public getFlows(filter: UnionFilters): Promise<Flow[]> {
    return this.post<IFlowResponse[]>('/filter', filter).then(response => this.mapFlowsResponse(response))
  }

  public getFlowsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  protected mapFlow(data: IFlowResponse): Flow {
    return new Flow({
      id: data.id,
      name: data.name,
      tags: data.tags,
      created: new Date(data.created),
      updated: new Date(data.updated),
    })
  }

  protected mapFlowResponse({ data }: AxiosResponse<IFlowResponse>): Flow {
    return this.mapFlow(data)
  }

  protected mapFlowsResponse({ data }: AxiosResponse<IFlowResponse[]>): Flow[] {
    return data.map(x => this.mapFlow(x))
  }

}

export const flowsApiKey: InjectionKey<FlowsApi> = Symbol('flowsApiKey')