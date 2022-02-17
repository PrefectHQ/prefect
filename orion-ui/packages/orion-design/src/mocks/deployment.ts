import { Deployment } from '@/models/Deployment'
import { MockFunction } from '@/services/Mocker'

export const randomDeployment: MockFunction<Deployment> = function() {
  return {
    id: this.create('string'),
    created: this.create('date'),
    updated: this.create('date'),
    name: this.create('string'),
    flowId: this.create('string'),
    isScheduleActive: this.create('boolean'),
    tags: this.createMany('string', 3),
    flowData: null,
    schedule: null,
    parameters: null,
  }
}