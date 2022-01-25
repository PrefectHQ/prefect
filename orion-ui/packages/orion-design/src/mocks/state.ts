import { MockGenerator } from '../mocks'
import { IState } from '../models'
import { mocker } from '../services'

export const randomState: MockGenerator<IState> = () => {
  const state: IState = {
    id: mocker.create('string'),
    type: mocker.create('stateType'),
    message: mocker.create('string'),
    stateDetails: {},
    data: {},
    timestamp: mocker.create('string'),
    name: mocker.create('string'),
  }

  return state
}