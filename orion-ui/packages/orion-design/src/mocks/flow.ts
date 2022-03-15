import { Flow } from '@/models/Flow'
import { MockFunction } from '@/services/Mocker'

export const randomFlow: MockFunction<Flow> = function(flow?: Partial<Flow>) {
  return new Flow({
    id: flow?.id ?? this.create('string'),
    created: flow?.created ?? this.create('date'),
    updated: flow?.updated ?? this.create('date'),
    name: flow?.name ?? this.create('string'),
    tags: flow?.tags ?? this.createMany('string', 3),
  })
}