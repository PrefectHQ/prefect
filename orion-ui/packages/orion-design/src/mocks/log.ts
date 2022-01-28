import { Log } from '../models'
import { mocker } from '../services'

export function randomLog(): Log {
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