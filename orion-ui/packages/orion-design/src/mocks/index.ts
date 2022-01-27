import { randomBoolean } from './boolean'
import { randomDate } from './date'
import { randomLog } from './log'
import { randomNumber } from './number'
import { randomState } from './state'
import { randomStateType } from './stateType'
import { randomChar, randomString, randomSentence, randomParagraph } from './string'
import { randomTaskRun } from './taskRun'

export const mocks = {
  boolean: randomBoolean,
  char: randomChar,
  date: randomDate,
  log: randomLog,
  number: randomNumber,
  paragraph: randomParagraph,
  sentence: randomSentence,
  state: randomState,
  stateType: randomStateType,
  string: randomString,
  taskRun: randomTaskRun,
}