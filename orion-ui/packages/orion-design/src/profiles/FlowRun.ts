import { FlowRun } from '@/models/FlowRun'
import { IFlowRunResponse } from '@/models/IFlowRunResponse'
import { Profile, translate } from '@/services/Translate'

export const flowRunProfile: Profile<IFlowRunResponse, FlowRun> = {
  toDestination(source) {
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
      startTime: source.start_time ? new Date(source.start_time) : null,
      endTime: source.end_time ? new Date(source.end_time) : null,
      name: source.name,
      parentTaskRunId: source.parent_task_run_id,
      stateId: source.state_id,
      stateType: source.state_type,
      state: source.state ? (this as typeof translate).toDestination('IStateResponse:IState', source.state) : null,
      tags: source.tags,
      runCount: source.run_count,
      created: new Date(source.created),
      updated: new Date(source.updated),
    })
  },
  toSource(destination) {
    return {
      'id': destination.id,
      'deployment_id': destination.deploymentId,
      'flow_id': destination.flowId,
      'flow_version': destination.flowVersion,
      'idempotency_key': destination.idempotencyKey,
      'expected_start_time': destination.expectedStartTime,
      'next_scheduled_start_time': destination.nextScheduledStartTime,
      'parameters': destination.parameters,
      'auto_scheduled': destination.autoScheduled,
      'context': destination.context,
      'empirical_config': destination.empiricalConfig,
      'empirical_policy': destination.empiricalPolicy,
      'estimated_run_time': destination.estimatedRunTime,
      'estimated_start_time_delta': destination.estimatedStartTimeDelta,
      'total_run_time': destination.totalRunTime,
      'start_time': destination.startTime?.toISOString() ?? null,
      'end_time': destination.endTime?.toISOString() ?? null,
      'name': destination.name,
      'parent_task_run_id': destination.parentTaskRunId,
      'state_id': destination.stateId,
      'state_type': destination.stateType,
      'state': destination.state ? (this as typeof translate).toSource('IStateResponse:IState', destination.state) : null,
      'tags': destination.tags,
      'run_count': destination.runCount,
      'created': destination.created.toISOString(),
      'updated': destination.updated.toISOString(),
      // doesn't exist on FlowRun?
      'flow_runner': null,
    }
  },
}