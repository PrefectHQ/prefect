import { TaskRun } from '../models'
import { mocker } from '../services'

export function randomTaskRun(): TaskRun {
  return new TaskRun({
    id: mocker.create('string'),
    flowRunId: mocker.create('string'),
    cacheExpiration: mocker.create('string'),
    cacheKey: mocker.create('string'),
    created: mocker.create('date'),
    dynamicKey: mocker.create('string'),
    empiricalPolicy: {},
    estimatedRunTime: mocker.create('number'),
    estimatedStartTimeDelta: mocker.create('number'),
    totalRunTime: mocker.create('number'),
    expectedStartTime: mocker.create('date'),
    nextScheduledStartTime: mocker.create('boolean') ? mocker.create('date') : null,
    runCount: mocker.create('number'),
    name: mocker.create('string'),
    taskInputs: {},
    taskKey: mocker.create('string'),
    taskVersion: mocker.create('string'),
    updated: mocker.create('date'),
    startTime: mocker.create('date'),
    endTime: mocker.create('date'),
    stateId: mocker.create('string'),
    stateType: mocker.create('stateType'),
    state: mocker.create('state'),
    duration: mocker.create('number'),
    subflowRuns: mocker.create('boolean'),
    tags: mocker.createMany('string', 3),
  })
}