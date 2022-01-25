import { randomBoolean } from './boolean'
import { randomDate } from './date'
import { randomLog } from './log'
import { randomNumber } from './number'
import { randomState } from './state'
import { randomStateType } from './stateType'
import { randomString } from './string'
import { randomTaskRun } from './taskRun'

export type MockGenerator<T> = (...args: any[]) => T

export const mockGenerators = {
  boolean: randomBoolean,
  date: randomDate,
  log: randomLog,
  number: randomNumber,
  state: randomState,
  stateType: randomStateType,
  string: randomString,
  taskRun: randomTaskRun,
}