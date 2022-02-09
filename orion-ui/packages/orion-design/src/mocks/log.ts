import { Log } from '../models'
import { MockFunction } from '../services'

export const randomLog: MockFunction<Log> = function() {
  return new Log({
    id: this.create('string'),
    created: this.create('date'),
    updated: this.create('date'),
    name: this.create('string'),
    level: this.create('number'),
    message: this.create('string'),
    timestamp: this.create('date'),
    flowRunId: this.create('string'),
    taskRunId: this.create('string'),
  })
}