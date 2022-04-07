import { ITaskRunResponse } from '@/models/ITaskRunResponse'
import { TaskRun } from '@/models/TaskRun'
import { MapFunction } from '@/services/Mapper'

export const mapITaskRunResponseToTaskRun: MapFunction<ITaskRunResponse, TaskRun> = function(source: ITaskRunResponse): TaskRun {
  return new TaskRun({
    id: source.id,
    flowRunId: source.flow_run_id,
    cacheExpiration: source.cache_expiration,
    cacheKey: source.cache_key,
    created: this.map('string', source.created, 'Date'),
    dynamicKey: source.dynamic_key,
    empiricalPolicy: source.empirical_policy ? this.map('IEmpiricalPolicyResponse', source.empirical_policy, 'EmpiricalPolicy') : null,
    estimatedRunTime: source.estimated_run_time,
    estimatedStartTimeDelta: source.estimated_start_time_delta,
    totalRunTime: source.total_run_time,
    expectedStartTime: source.expected_start_time ? this.map('string', source.expected_start_time, 'Date') : null,
    nextScheduledStartTime: source.next_scheduled_start_time,
    runCount: source.run_count,
    name: source.name,
    taskInputs: source.task_inputs ? this.mapEntries('ITaskInputResponse', source.task_inputs, 'TaskInput') : null,
    taskKey: source.task_key,
    taskVersion: source.task_version,
    updated: this.map('string', source.updated, 'Date'),
    startTime: source.start_time ? this.map('string', source.start_time, 'Date') : null,
    endTime: source.end_time ? this.map('string', source.end_time, 'Date') : null,
    stateId: source.state_id,
    stateType: source.state_type,
    state: source.state ? this.map('IStateResponse', source.state, 'IState') : null,
    tags: source.tags,
  })
}

export const mapTaskRunToITaskRunResponse: MapFunction<TaskRun, ITaskRunResponse> = function(source: TaskRun): ITaskRunResponse {
  return {
    'id': source.id,
    'flow_run_id': source.flowRunId,
    'cache_expiration': source.cacheExpiration,
    'cache_key': source.cacheKey,
    'created': this.map('Date', source.created, 'string'),
    'dynamic_key': source.dynamicKey,
    'empirical_policy': source.empiricalPolicy ? this.map('EmpiricalPolicy', source.empiricalPolicy, 'IEmpiricalPolicyResponse') : null,
    'estimated_run_time': source.estimatedRunTime,
    'estimated_start_time_delta': source.estimatedStartTimeDelta,
    'total_run_time': source.totalRunTime,
    'expected_start_time': source.expectedStartTime ? this.map('Date', source.expectedStartTime, 'string') : null,
    'next_scheduled_start_time': source.nextScheduledStartTime,
    'run_count': source.runCount,
    'name': source.name,
    'task_inputs': source.taskInputs ? this.mapEntries('TaskInput', source.taskInputs, 'ITaskInputResponse') : null,
    'task_key': source.taskKey,
    'task_version': source.taskVersion,
    'updated': this.map('Date', source.updated, 'string'),
    'start_time': source.startTime ? this.map('Date', source.startTime, 'string') : null,
    'end_time': source.endTime ? this.map('Date', source.endTime, 'string') : null,
    'state_id': source.stateId,
    'state_type': source.stateType,
    'state': source.state ? this.map('IState', source.state, 'IStateResponse') : null,
    'tags': source.tags,
  }
}