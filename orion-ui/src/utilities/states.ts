import { State, States } from '@/types/states'

export function isState(value: unknown): value is State {
  return Object.values(States).includes(value)
}
