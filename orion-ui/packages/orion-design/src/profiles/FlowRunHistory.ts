import { IFlowRunHistoryResponse } from '@/models/IFlowRunHistoryResponse'
import { RunHistory } from '@/models/RunHistory'
import { Profile, translate } from '@/services/Translate'

export const flowRunHistoryProfile: Profile<IFlowRunHistoryResponse, RunHistory> = {
  toDestination(source) {
    return new RunHistory({
      intervalStart: new Date(source.interval_start),
      intervalEnd: new Date(source.interval_end),
      states: source.states.map(x => (this as typeof translate).toDestination('IStateHistoryResponse:StateHistory', x)),
    })
  },
  toSource(destination) {
    return {
      'interval_start': destination.intervalStart,
      'interval_end': destination.intervalEnd,
      'states': destination.states.map(x => (this as typeof translate).toSource('IStateHistoryResponse:StateHistory', x)),
    }
  },
}