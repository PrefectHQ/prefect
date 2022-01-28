import { stateType } from '../models'
import { MockerFunction } from '../services'
import type { StateType } from '../types'

export const randomStateType: MockerFunction<StateType> = function() {
  return stateType[Math.floor(Math.random() * stateType.length)]
}