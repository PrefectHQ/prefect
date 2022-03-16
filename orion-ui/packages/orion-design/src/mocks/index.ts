import { randomBoolean } from './boolean'
import { randomDate } from './date'
import { randomDeployment } from './deployment'
import { randomFlow } from './flow'
import { randomFlowRun } from './flowRun'
import { randomFlowRunHistory } from './flowRunHistory'
import { randomFlowRunnerType } from './flowRunnerType'
import { randomFlowRunStateHistory } from './flowRunStateHistory'
import { randomLog } from './log'
import { randomNumber } from './number'
import { randomState } from './state'
import { randomStateType } from './stateType'
import { randomChar, randomString, randomSentence, randomParagraph } from './string'
import { randomTaskRun } from './taskRun'
import { randomWorkQueue, randomWorkQueueFilter } from './workQueue'

export const mocks = {
  boolean: randomBoolean,
  char: randomChar,
  date: randomDate,
  deployment: randomDeployment,
  flow: randomFlow,
  flowRun: randomFlowRun,
  log: randomLog,
  number: randomNumber,
  paragraph: randomParagraph,
  sentence: randomSentence,
  state: randomState,
  stateType: randomStateType,
  string: randomString,
  taskRun: randomTaskRun,
  workQueue: randomWorkQueue,
  workQueueFilter: randomWorkQueueFilter,
  flowRunnerType: randomFlowRunnerType,
  flowRunHistory: randomFlowRunHistory,
  flowRunStateHistory: randomFlowRunStateHistory,
}