import { randomBoolean } from './boolean'
import { randomDate } from './date'
import { randomDeployment } from './deployment'
import { randomFlowRun } from './flowRun'
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
  deployment: randomDeployment,
  flowRun: randomFlowRun,
  log: randomLog,
  number: randomNumber,
  paragraph: randomParagraph,
  sentence: randomSentence,
  state: randomState,
  stateType: randomStateType,
  string: randomString,
  taskRun: randomTaskRun,
}