import { randomBoolean } from './boolean'
import { randomDate } from './date'
import { randomNumber } from './number'
import { randomString } from './string'

export type MockGenerator<T> = (...args: any[]) => T

export const mockGenerators = {
  boolean: randomBoolean,
  date: randomDate,
  number: randomNumber,
  string: randomString,
}