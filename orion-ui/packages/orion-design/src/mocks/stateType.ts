import { stateType } from '../models'
import { MockFunction } from '../services'
import type { StateType } from '../types'

export const randomStateType: MockFunction<StateType> = function() {
  return stateType[Math.floor(Math.random() * stateType.length)]
}