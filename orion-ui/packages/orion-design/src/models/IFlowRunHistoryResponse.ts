import { IStateHistoryResponse } from '@/models/IStateHistoryResponse'

export type IFlowRunHistoryResponse = {
  interval_start: Date,
  interval_end: Date,
  states: IStateHistoryResponse[],
}