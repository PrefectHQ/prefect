import { MockGenerator } from '../mocks'
import { stateType } from '../models'
import type { StateType } from '../types'

export const randomStateType: MockGenerator<StateType> = () => {
  return stateType[Math.floor(Math.random() * stateType.length)]
}