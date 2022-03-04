import { WorkQueueFilter } from '@/models'
import { WorkQueue } from '@/models/WorkQueue'
import { MockFunction } from '@/services/Mocker'

export const randomWorkQueue: MockFunction<WorkQueue> = function() {
  return new WorkQueue({
    id: this.create('string'),
    created: this.create('date'),
    updated: this.create('date'),
    name: this.create('string'),
    filter: this.create('workQueueFilter'),
    description: this.create('string'),
    isPaused: this.create('boolean'),
    concurrencyLimit: this.create('number'),
  })
}

export const randomWorkQueueFilter: MockFunction<WorkQueueFilter> = function() {
  return new WorkQueueFilter({
    tags: this.createMany('string', 3),
    deploymentIds: this.createMany('string', 3),
    flowRunnerTypes: this.createMany('string', 3),
  })
}