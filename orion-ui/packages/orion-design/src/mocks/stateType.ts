import { stateType } from '../models'
import type { StateType } from '../models'
import { MockFunction } from '../services'

export const randomStateType: MockFunction<StateType> = function() {
  return stateType[Math.floor(Math.random() * stateType.length)]
}