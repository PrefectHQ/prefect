import { IStateHistoryResponse } from '@/models/IStateHistoryResponse'
import { StateHistory } from '@/models/StateHistory'
import { Profile } from '@/services/Translate'
import { StateName } from '@/types/states'


export const stateHistoryProfile: Profile<IStateHistoryResponse, StateHistory> = {
  toDestination(source) {
    return new StateHistory({
      stateType: source.state_type,
      stateName: source.state_name,
      countRuns: source.count_runs,
      sumEstimatedRunTime: source.sum_estimated_run_time,
      sumEstimatedLateness: source.sum_estimated_lateness,
    })
  },
  toSource(destination) {
    return {
      'state_type': destination.stateType,
      'state_name': destination.stateName as StateName,
      'count_runs': destination.countRuns,
      'sum_estimated_run_time': destination.sumEstimatedRunTime,
      'sum_estimated_lateness': destination.sumEstimatedLateness,
    }
  },
}