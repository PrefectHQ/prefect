import { FlowRun } from '@/models/FlowRun'
import { MockFunction } from '@/services/Mocker'

export const randomFlowRun: MockFunction<FlowRun> = function(flowRun?: Partial<FlowRun>) {
  return new FlowRun({
    id: flowRun?.id ?? this.create('string'),
    flowId: flowRun?.flowId ?? this.create('string'),
    deploymentId: flowRun?.deploymentId ?? this.create('string'),
    flowVersion: flowRun?.flowVersion ?? this.create('string'),
    idempotencyKey: flowRun?.idempotencyKey ?? this.create('string'),
    expectedStartTime: flowRun?.expectedStartTime ?? this.create('string'),
    nextScheduledStartTime: flowRun?.nextScheduledStartTime ?? this.create('string'),
    parameters: flowRun?.parameters ?? {},
    autoScheduled: flowRun?.autoScheduled ?? this.create('boolean'),
    context: flowRun?.context ?? {},
    empiricalConfig: flowRun?.empiricalConfig ?? {},
    empiricalPolicy: flowRun?.empiricalPolicy ?? {},
    estimatedRunTime: flowRun?.estimatedRunTime ?? this.create('number'),
    estimatedStartTimeDelta: flowRun?.estimatedStartTimeDelta ?? this.create('number'),
    totalRunTime: flowRun?.totalRunTime ?? this.create('number'),
    startTime: flowRun?.startTime ?? this.create('date'),
    endTime: flowRun?.endTime ?? this.create('date'),
    name: flowRun?.name ?? this.create('string'),
    parentTaskRunId: flowRun?.parentTaskRunId ?? this.create('string'),
    stateId: flowRun?.stateId ?? this.create('string'),
    stateType: flowRun?.stateType ?? this.create('stateType'),
    state: flowRun?.state ?? this.create('state'),
    tags: flowRun?.tags ?? this.createMany('string', 3),
    runCount: flowRun?.runCount ?? this.create('number'),
    created: flowRun?.created ?? this.create('date'),
    updated: flowRun?.updated ?? this.create('date'),
  })
}