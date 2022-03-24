import { ITaskRunResponse } from '@/models/ITaskRunResponse'
import { TaskRun } from '@/models/TaskRun'
import { Profile, translate } from '@/services/Translate'

export const taskRunProfile: Profile<ITaskRunResponse, TaskRun> = {
  toDestination(source) {
    return new TaskRun({
      id: source.id,
      flowRunId: source.flow_run_id,
      cacheExpiration: source.cache_expiration,
      cacheKey: source.cache_key,
      created: new Date(source.created),
      dynamicKey: source.dynamic_key,
      empiricalPolicy: source.empirical_policy ? (this as typeof translate).toDestination('IEmpiricalPolicyResponse:EmpiricalPolicy', source.empirical_policy) : null,
      estimatedRunTime: source.estimated_run_time,
      estimatedStartTimeDelta: source.estimated_start_time_delta,
      totalRunTime: source.total_run_time,
      expectedStartTime: source.expected_start_time ? new Date(source.expected_start_time) : null,
      nextScheduledStartTime: source.next_scheduled_start_time,
      runCount: source.run_count,
      name: source.name,
      taskInputs: source.task_inputs ? (this as typeof translate).toDestination('ITaskInputResponseRecord:TaskInputRecord', source.task_inputs) : null,
      taskKey: source.task_key,
      taskVersion: source.task_version,
      updated: new Date(source.updated),
      startTime: source.start_time ? new Date(source.start_time) : null,
      endTime: source.end_time ? new Date(source.end_time) : null,
      stateId: source.state_id,
      stateType: source.state_type,
      state: source.state ? (this as typeof translate).toDestination('IStateResponse:IState', source.state) : null,
      tags: source.tags,
    })
  },
  toSource(destination) {
    return {
      'id': destination.id,
      'flow_run_id': destination.flowRunId,
      'cache_expiration': destination.cacheExpiration,
      'cache_key': destination.cacheKey,
      'created': destination.created.toISOString(),
      'dynamic_key': destination.dynamicKey,
      'empirical_policy': destination.empiricalPolicy ? (this as typeof translate).toSource('IEmpiricalPolicyResponse:EmpiricalPolicy', destination.empiricalPolicy) : null,
      'estimated_run_time': destination.estimatedRunTime,
      'estimated_start_time_delta': destination.estimatedStartTimeDelta,
      'total_run_time': destination.totalRunTime,
      'expected_start_time': destination.expectedStartTime?.toISOString() ?? null,
      'next_scheduled_start_time': destination.nextScheduledStartTime,
      'run_count': destination.runCount,
      'name': destination.name,
      'task_inputs': destination.taskInputs ? (this as typeof translate).toSource('ITaskInputResponseRecord:TaskInputRecord', destination.taskInputs) : null,
      'task_key': destination.taskKey,
      'task_version': destination.taskVersion,
      'updated': destination.updated.toISOString(),
      'start_time': destination.startTime?.toISOString() ?? null,
      'end_time': destination.endTime?.toISOString() ?? null,
      'state_id': destination.stateId,
      'state_type': destination.stateType,
      'state': destination.state ? (this as typeof translate).toSource('IStateResponse:IState', destination.state) : null,
      'tags': destination.tags,
    }
  },
}