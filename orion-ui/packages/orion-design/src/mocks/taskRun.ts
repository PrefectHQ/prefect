import { TaskRun } from '@/models/TaskRun'
import { MockFunction } from '@/services/Mocker'

export const randomTaskRun: MockFunction<TaskRun> = function() {
  return new TaskRun({
    id: this.create('string'),
    flowRunId: this.create('string'),
    cacheExpiration: this.create('string'),
    cacheKey: this.create('string'),
    created: this.create('date'),
    dynamicKey: this.create('string'),
    empiricalPolicy: null,
    estimatedRunTime: this.create('number'),
    estimatedStartTimeDelta: this.create('number'),
    totalRunTime: this.create('number'),
    expectedStartTime: this.create('date'),
    nextScheduledStartTime: this.create('boolean') ? this.create('string') : null,
    runCount: this.create('number'),
    name: this.create('string'),
    taskInputs: {},
    taskKey: this.create('string'),
    taskVersion: this.create('string'),
    updated: this.create('date'),
    startTime: this.create('date'),
    endTime: this.create('date'),
    stateId: this.create('string'),
    stateType: this.create('stateType'),
    state: this.create('state'),
    tags: this.createMany('string', 3),
  })
}