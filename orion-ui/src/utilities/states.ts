import { StateType, States } from '@/types/states'

export function isState(value: unknown): value is StateType {
  return Object.values(States).includes(value)
}
