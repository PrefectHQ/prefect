import { IState } from '../models'
import { MockerFunction } from '../services'

export const randomState: MockerFunction<IState> = function() {
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