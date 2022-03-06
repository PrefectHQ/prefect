import { TaskRun } from '@/models/TaskRun'
import { MockFunction } from '@/services/Mocker'

export const randomTaskRun: MockFunction<TaskRun> = function(taskRun: Partial<TaskRun>) {
  return new TaskRun({
    id: taskRun.id ?? this.create('string'),
    flowRunId: taskRun.flowRunId ?? this.create('string'),
    cacheExpiration: taskRun.cacheExpiration ?? this.create('string'),
    cacheKey: taskRun.cacheKey ?? this.create('string'),
    created: taskRun.created ?? this.create('date'),
    dynamicKey: taskRun.dynamicKey ?? this.create('string'),
    empiricalPolicy: taskRun.empiricalPolicy ?? null,
    estimatedRunTime: taskRun.estimatedRunTime ?? this.create('number'),
    estimatedStartTimeDelta: taskRun.estimatedStartTimeDelta ?? this.create('number'),
    totalRunTime: taskRun.totalRunTime ?? this.create('number'),
    expectedStartTime: taskRun.expectedStartTime ?? this.create('date'),
    nextScheduledStartTime: taskRun.nextScheduledStartTime ?? this.create('boolean') ? this.create('string') : null,
    runCount: taskRun.runCount ?? this.create('number'),
    name: taskRun.name ?? this.create('string'),
    taskInputs: taskRun.taskInputs ?? {},
    taskKey: taskRun.taskKey ?? this.create('string'),
    taskVersion: taskRun.taskVersion ?? this.create('string'),
    updated: taskRun.updated ?? this.create('date'),
    startTime: taskRun.startTime ?? this.create('date'),
    endTime: taskRun.endTime ?? this.create('date'),
    stateId: taskRun.stateId ?? this.create('string'),
    stateType: taskRun.stateType ?? this.create('stateType'),
    state: taskRun.state ?? this.create('state'),
    tags: taskRun.tags ?? this.createMany('string', 3),
  })
}