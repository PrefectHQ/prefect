import { WorkQueue } from '@/models/WorkQueue'
import { WorkQueueFilter } from '@/models/WorkQueueFilter'
import { MockFunction } from '@/services/Mocker'

export const randomWorkQueue: MockFunction<WorkQueue> = function(workQueue?: Partial<WorkQueue>) {
  return new WorkQueue({
    id: workQueue?.id ?? this.create('string'),
    created: workQueue?.created ?? this.create('date'),
    updated: workQueue?.updated ?? this.create('date'),
    name: workQueue?.name ?? this.create('string'),
    filter: this.create('workQueueFilter', [workQueue?.filter]),
    description: workQueue?.description ?? this.create('string'),
    isPaused: workQueue?.isPaused ?? this.create('boolean'),
    concurrencyLimit: workQueue?.concurrencyLimit ?? this.create('number'),
  })
}

export const randomWorkQueueFilter: MockFunction<WorkQueueFilter> = function(workQueueFilter?: Partial<WorkQueueFilter>) {
  return new WorkQueueFilter({
    tags: workQueueFilter?.tags ?? this.createMany('string', 3),
    deploymentIds: workQueueFilter?.deploymentIds ?? this.createMany('string', 3),
    flowRunnerTypes: workQueueFilter?.flowRunnerTypes ?? this.createMany('flowRunnerType', 3),
  })
}