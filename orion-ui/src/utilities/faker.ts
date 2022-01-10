import { StateType, States } from '@/types/states'
import faker from 'faker'

type NumberOptions = {
  min?: number | undefined
  max?: number | undefined
  precision?: number | undefined
}
type FakerCallback = () => any

export function fakerArray(length: number, callback: () => any) {
  return new Array(length).fill(null).map(callback)
}

export function fakerRandomArray<T extends FakerCallback>(
  options: NumberOptions,
  callback: T
): ReturnType<T>[]
export function fakerRandomArray<T extends FakerCallback>(
  max: number,
  callback: T
): ReturnType<T>[]
export function fakerRandomArray<T extends FakerCallback>(
  maxOrOptions: number | NumberOptions,
  callback: T
): ReturnType<T>[] {
  const length = faker.datatype.number(maxOrOptions)

  return fakerArray(length, callback)
}

export function fakerRandomState(
  states: StateType[] = Object.values(States)
): StateType {
  return states[faker.datatype.number(states.length - 1)]
}
