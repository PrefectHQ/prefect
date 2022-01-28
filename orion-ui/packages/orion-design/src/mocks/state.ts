import { IState } from '../models'
import { mocker } from '../services'

export function randomState(): IState {
  return {
    id: mocker.create('string'),
    type: mocker.create('stateType'),
    message: mocker.create('string'),
    stateDetails: {},
    data: {},
    timestamp: mocker.create('string'),
    name: mocker.create('string'),
  }
}