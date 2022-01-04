import Flow from '@/models/flow'
import { FlowsFilter } from '@/plugins/api'
import { createApi } from '@/utilities/api'
import { AxiosResponse } from 'axios'

const API = createApi('/flows')

interface IFlowResponse {
  id: string
  name: string
  flow_id: string
  deployment_id: string
  flow_version: string
  parameters: unknown
  created: string
  updated: string
  tags: string[]
}

interface IPostFlowRequest extends FlowsFilter {
  name?: string
  flow_id: string
  deployment_id?: string
  flow_version?: string
  parameters?: unknown
  tags?: string[]
}

function flowMapper(flow: IFlowResponse): Flow {
  return new Flow({
    id: flow.id,
    created: new Date(flow.created),
    updated: new Date(flow.updated),
    name: flow.name,
    tags: flow.tags
  })
}

function flowResponseMapper({ data }: AxiosResponse<IFlowResponse>): Flow {
  return flowMapper(data)
}

function flowsResponseMapper({ data }: AxiosResponse<IFlowResponse[]>): Flow[] {
  return data.map(flowMapper)
}

export default class FlowsApi {
  public static PostFlow(flow: IPostFlowRequest): Promise<Flow> {
    return API.post<IFlowResponse>('', flow).then(flowResponseMapper)
  }

  public static GetFlow(id: string): Promise<Flow> {
    return API.get<IFlowResponse>(id).then(flowResponseMapper)
  }

  public static DeleteFlow(id: string): Promise<void> {
    return API.delete<void>(id).then((response) => response.data)
  }

  public static PatchFlow(id: string, body: Partial<Flow>): Promise<void> {
    return API.patch<void>(id, body).then((response) => response.data)
  }

  public static GetCount(body: FlowsFilter): Promise<number> {
    return API.post<number>('count', body).then((response) => response.data)
  }

  public static GetByName(name: string): Promise<Flow> {
    return API.post<IFlowResponse>(`name/${name}`).then(flowResponseMapper)
  }

  public static Filter(body: FlowsFilter): Promise<Flow[]> {
    return API.post<IFlowResponse[]>('filter', body).then(flowsResponseMapper)
  }
}
