import { SubState, SubStates, State, States } from '@/types/states'

export function isState(value: unknown): value is State {
  return Object.values(States).includes(value)
}

export function isSubState(value: unknown): value is SubState {
  return SubStates.includes(value as SubState)
}
