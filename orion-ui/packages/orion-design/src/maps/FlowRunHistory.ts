import { IFlowRunHistoryResponse } from '@/models/IFlowRunHistoryResponse'
import { RunHistory } from '@/models/RunHistory'
import { MapFunction } from '@/services/Mapper'

export const mapIFlowRunHistoryResponseToRunHistory: MapFunction<IFlowRunHistoryResponse, RunHistory> = function(source: IFlowRunHistoryResponse): RunHistory {
  return new RunHistory({
    intervalStart: source.interval_start,
    intervalEnd: source.interval_end,
    states: this.map('IStateHistoryResponse', source.states, 'StateHistory'),
  })
}

export const mapRunHistoryToIFlowRunHistoryResponse: MapFunction<RunHistory, IFlowRunHistoryResponse> = function(source: RunHistory): IFlowRunHistoryResponse {
  return {
    'interval_start': source.intervalStart,
    'interval_end': source.intervalEnd,
    'states': this.map('StateHistory', source.states, 'IStateHistoryResponse'),
  }
}