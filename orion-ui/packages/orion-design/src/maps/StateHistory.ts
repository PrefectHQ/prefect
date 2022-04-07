import { IStateHistoryResponse } from '@/models/IStateHistoryResponse'
import { StateHistory } from '@/models/StateHistory'
import { MapFunction } from '@/services/Mapper'
import { StateName } from '@/types/states'


export const mapIStateHistoryResponseToStateHistory: MapFunction<IStateHistoryResponse, StateHistory> = function(source: IStateHistoryResponse): StateHistory {
  return new StateHistory({
    stateType: source.state_type,
    stateName: source.state_name,
    countRuns: source.count_runs,
    sumEstimatedRunTime: source.sum_estimated_run_time,
    sumEstimatedLateness: source.sum_estimated_lateness,
  })
}

export const mapStateHistoryToIStateHistoryResponse: MapFunction<StateHistory, IStateHistoryResponse> = function(source: StateHistory): IStateHistoryResponse {
  return {
    'state_type': source.stateType,
    'state_name': source.stateName as StateName,
    'count_runs': source.countRuns,
    'sum_estimated_run_time': source.sumEstimatedRunTime,
    'sum_estimated_lateness': source.sumEstimatedLateness,
  }
}