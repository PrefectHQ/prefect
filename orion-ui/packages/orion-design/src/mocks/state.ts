import { IState } from '@/models/State'
import { MockFunction } from '@/services/Mocker'

export const randomState: MockFunction<IState> = function() {
  return {
    id: this.create('string'),
    type: this.create('stateType'),
    message: this.create('string'),
    stateDetails: {
      flowRunId: this.create('string'),
      taskRunId: this.create('string'),
      childFlowRunId: this.create('string'),
      scheduledTime: this.create('date'),
      cacheKey: this.create('string'),
      cacheExpiration: this.create('date'),
    },
    data: {
      encoding: this.create('string'),
      blob: this.create('string'),
    },
    timestamp: this.create('string'),
    name: this.create('string'),
  }
}