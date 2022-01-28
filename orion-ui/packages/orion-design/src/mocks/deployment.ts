import { Deployment } from '../models'
import { mocker } from '../services'

export function randomDeployment(): Deployment {
  return {
    id: mocker.create('string'),
    created: mocker.create('date'),
    updated: mocker.create('date'),
    name: mocker.create('string'),
    flowId: mocker.create('string'),
    isScheduleActive: mocker.create('boolean'),
    tags: mocker.createMany('string', 3),
    flowData: null,
    schedule: null,
    parameters: null,
  }
}