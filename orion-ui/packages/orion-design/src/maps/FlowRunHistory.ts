import { IFlowRunHistoryResponse } from '@/models/IFlowRunHistoryResponse'
import { RunHistory } from '@/models/RunHistory'
import { MapFunction } from '@/services/Mapper'

export const mapIFlowRunHistoryResponseToRunHistory: MapFunction<IFlowRunHistoryResponse, RunHistory> = function(source: IFlowRunHistoryResponse): RunHistory {
  return new RunHistory({
    intervalStart: this.map('string', source.interval_start, 'Date'),
    intervalEnd: this.map('string', source.interval_end, 'Date'),
    states: this.map('IStateHistoryResponse', source.states, 'StateHistory'),
  })
}

export const mapRunHistoryToIFlowRunHistoryResponse: MapFunction<RunHistory, IFlowRunHistoryResponse> = function(source: RunHistory): IFlowRunHistoryResponse {
  return {
    'interval_start': this.map('Date', source.intervalStart, 'string'),
    'interval_end': this.map('Date', source.intervalEnd, 'string'),
    'states': this.map('StateHistory', source.states, 'IStateHistoryResponse'),
  }
}