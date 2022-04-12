import { FlowRun } from '@/models/FlowRun'
import { IFlowRunResponse } from '@/models/IFlowRunResponse'
import { MapFunction } from '@/services/Mapper'

export const mapIFlowRunResponseToFlowRun: MapFunction<IFlowRunResponse, FlowRun> = function(source: IFlowRunResponse): FlowRun {
  return new FlowRun({
    id: source.id,
    deploymentId: source.deployment_id,
    flowId: source.flow_id,
    flowVersion: source.flow_version,
    idempotencyKey: source.idempotency_key,
    expectedStartTime: source.expected_start_time,
    nextScheduledStartTime: source.next_scheduled_start_time,
    parameters: source.parameters,
    autoScheduled: source.auto_scheduled,
    context: source.context,
    empiricalConfig: source.empirical_config,
    empiricalPolicy: source.empirical_policy,
    estimatedRunTime: source.estimated_run_time,
    estimatedStartTimeDelta: source.estimated_start_time_delta,
    totalRunTime: source.total_run_time,
    startTime: this.map('string', source.start_time, 'Date'),
    endTime: this.map('string', source.end_time, 'Date'),
    name: source.name,
    parentTaskRunId: source.parent_task_run_id,
    stateId: source.state_id,
    stateType: source.state_type,
    state: this.map('IStateResponse', source.state, 'IState'),
    tags: source.tags,
    runCount: source.run_count,
    created: this.map('string', source.created, 'Date'),
    updated: this.map('string', source.updated, 'Date'),
  })
}

export const mapFlowRunToIFlowRunResponse: MapFunction<FlowRun, IFlowRunResponse> = function(source: FlowRun): IFlowRunResponse {
  return {
    'id': source.id,
    'deployment_id': source.deploymentId,
    'flow_id': source.flowId,
    'flow_version': source.flowVersion,
    'idempotency_key': source.idempotencyKey,
    'expected_start_time': source.expectedStartTime,
    'next_scheduled_start_time': source.nextScheduledStartTime,
    'parameters': source.parameters,
    'auto_scheduled': source.autoScheduled,
    'context': source.context,
    'empirical_config': source.empiricalConfig,
    'empirical_policy': source.empiricalPolicy,
    'estimated_run_time': source.estimatedRunTime,
    'estimated_start_time_delta': source.estimatedStartTimeDelta,
    'total_run_time': source.totalRunTime,
    'start_time': this.map('Date', source.startTime, 'string'),
    'end_time': this.map('Date', source.endTime, 'string'),
    'name': source.name,
    'parent_task_run_id': source.parentTaskRunId,
    'state_id': source.stateId,
    'state_type': source.stateType,
    'state': this.map('IState', source.state, 'IStateResponse'),
    'tags': source.tags,
    'run_count': source.runCount,
    'created': this.map('Date', source.created, 'string'),
    'updated': this.map('Date', source.updated, 'string'),
    // doesn't exist on FlowRun?
    'flow_runner': null,
  }
}