import { IState } from '@/models/State'
import { MockFunction } from '@/services/Mocker'

export const randomState: MockFunction<IState> = function() {
  return {
    id: this.create('string'),
    type: this.create('stateType'),
    message: this.create('string'),
    stateDetails: {},
    data: {},
    timestamp: this.create('string'),
    name: this.create('string'),
  }
}