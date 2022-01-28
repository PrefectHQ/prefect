import { FlowRun } from '../models'
import { mocker } from '../services'

export function randomFlowRun(): FlowRun {
  return {
    id: mocker.create('string'),
    deploymentId: mocker.create('string'),
    flowId: mocker.create('string'),
    flowVersion: mocker.create('string'),
    idempotencyKey: mocker.create('boolean') ? mocker.create('string') : null,
    nextScheduledStartTime: mocker.create('boolean') ? mocker.create('string') : null,
    autoScheduled: mocker.create('boolean'),
    estimatedRunTime: mocker.create('number'),
    estimatedStartTimeDelta: mocker.create('number'),
    totalRunTime: mocker.create('number'),
    startTime: mocker.create('date'),
    endTime: mocker.create('date'),
    name: mocker.create('string'),
    parentTaskRunId: mocker.create('string'),
    stateId: mocker.create('string'),
    stateType: mocker.create('stateType'),
    state: mocker.create('state'),
    tags: mocker.createMany('string', 3),
    taskRunCount: mocker.create('number'),
    updated: mocker.create('date'),
    parameters: null,
    context: null,
    empericalConfig: null,
    empericalPolicy: null,
  }
}