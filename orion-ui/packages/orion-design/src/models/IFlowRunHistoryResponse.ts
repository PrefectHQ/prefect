import { IStateHistoryResponse } from '@/models/IStateHistoryResponse'

export type IFlowRunHistoryResponse = {
  interval_start: string,
  interval_end: string,
  states: IStateHistoryResponse[],
}