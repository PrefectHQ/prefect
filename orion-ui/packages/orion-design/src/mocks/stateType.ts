import { stateType } from '../models'
import type { StateType } from '../types'

export function randomStateType(): StateType {
  return stateType[Math.floor(Math.random() * stateType.length)]
}