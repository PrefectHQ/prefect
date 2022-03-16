import { StateHistory } from '@/models/StateHistory'
import { MockFunction } from '@/services/Mocker'

export const randomFlowRunStateHistory: MockFunction<StateHistory> = function(state?: Partial<StateHistory>) {
  return new StateHistory({
    stateType: state?.stateType ?? this.create('stateType'),
    stateName: state?.stateName ?? this.create('string'),
    countRuns: state?.countRuns ?? this.create('number'),
    sumEstimatedLateness: state?.sumEstimatedLateness ?? this.create('number'),
    sumEstimatedRunTime: state?.sumEstimatedRunTime ?? this.create('number'),
  })
}