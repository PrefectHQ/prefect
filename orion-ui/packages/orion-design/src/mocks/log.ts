import { Log } from '../models'
import { mocker as Mocker } from '../services'

export function randomLog(mocker: typeof Mocker): Log {
  return new Log({
    id: mocker.create('string'),
    created: mocker.create('date'),
    updated: mocker.create('date'),
    name: mocker.create('string'),
    level: mocker.create('number'),
    message: mocker.create('string'),
    timestamp: mocker.create('date'),
    flowRunId: mocker.create('string'),
    taskRunId: mocker.create('string'),
  })
}