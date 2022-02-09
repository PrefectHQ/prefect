import { FlowRun } from '../models'
import { MockFunction } from '../services'

export const randomFlowRun: MockFunction<FlowRun> = function() {
  return {
    id: this.create('string'),
    deploymentId: this.create('string'),
    flowId: this.create('string'),
    flowVersion: this.create('string'),
    idempotencyKey: this.create('boolean') ? this.create('string') : null,
    nextScheduledStartTime: this.create('boolean') ? this.create('string') : null,
    autoScheduled: this.create('boolean'),
    estimatedRunTime: this.create('number'),
    estimatedStartTimeDelta: this.create('number'),
    totalRunTime: this.create('number'),
    startTime: this.create('date'),
    endTime: this.create('date'),
    name: this.create('string'),
    parentTaskRunId: this.create('string'),
    stateId: this.create('string'),
    stateType: this.create('stateType'),
    state: this.create('state'),
    tags: this.createMany('string', 3),
    taskRunCount: this.create('number'),
    updated: this.create('date'),
    parameters: null,
    context: null,
    empericalConfig: null,
    empericalPolicy: null,
  }
}