import FlowRunHistory from '@/models/flowRunHistory'
import { IFlowRunStateHistory } from '@/models/flowRunStateHistory'
import { HistoryFilter } from '@prefecthq/orion-design'
import { createApi } from '@/utilities/api'
import { AxiosResponse } from 'axios'

const API = createApi('/flow_runs')

interface IFlowRunHistoryResponse {
  interval_start: string
  interval_end: string
  states: IFlowRunStateHistory[]
}

function flowRunHistoryMapper(flow: IFlowRunHistoryResponse): FlowRunHistory {
  return new FlowRunHistory({
    interval_start: new Date(flow.interval_start),
    interval_end: new Date(flow.interval_end),
    states: flow.states
  })
}

function flowRunHistoryResponseMapper(
  response: AxiosResponse<IFlowRunHistoryResponse[]>
): FlowRunHistory[] {
  return response.data.map(flowRunHistoryMapper)
}

export default class FlowRunsApi {
  public static History(filter: HistoryFilter): Promise<FlowRunHistory[]> {
    return API.post<IFlowRunHistoryResponse[]>('/history', filter).then(
      flowRunHistoryResponseMapper
    )
  }
}
