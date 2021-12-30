import FlowRun, { IFlowRun } from './flowRun'
import faker from 'faker'
import { fakerRandomArray, fakerRandomState } from '@/utilities/faker'
import addSeconds from 'date-fns/addSeconds'
import StateMock from './stateMock'

function time(max = 100) {
  return faker.datatype.float({ min: 0.01, max, precision: 6 })
}

export default class FlowRunMock extends FlowRun {
  constructor(flow: Partial<IFlowRun> = {}) {
    const total_run_time = flow.total_run_time ?? time()
    const start_time = faker.date.recent(7)
    const end_time = addSeconds(new Date(start_time), total_run_time)
    const updated = faker.date.between(start_time, new Date())
    const state_type = fakerRandomState()
    const state_id = faker.datatype.uuid()

    super({
      id: flow.id ?? faker.datatype.uuid(),
      deployment_id: flow.deployment_id ?? faker.datatype.uuid(),
      flow_id: flow.flow_id ?? faker.datatype.uuid(),
      flow_version: flow.flow_version ?? faker.datatype.uuid(),
      idempotency_key: flow.idempotency_key ?? null,
      next_scheduled_start_time: flow.next_scheduled_start_time ?? null,
      parameters: flow.parameters ?? {},
      auto_scheduled: flow.auto_scheduled ?? false,
      context: flow.context ?? {},
      emperical_config: flow.emperical_config ?? {},
      emperical_policy: flow.emperical_policy ?? {},
      estimated_run_time: flow.estimated_run_time ?? time(),
      estimated_start_time_delta: flow.estimated_start_time_delta ?? time(5),
      total_run_time: flow.total_run_time ?? time(),
      start_time,
      end_time,
      name: flow.name ?? faker.lorem.slug(2),
      parent_task_run_id: flow.parent_task_run_id ?? faker.datatype.uuid(),
      state_id: flow.state_id ?? state_id,
      state_type: flow.state_type ?? state_type,
      state: flow.state ?? new StateMock({ id: state_id, type: state_type }),
      tags: flow.tags ?? fakerRandomArray(5, () => faker.lorem.word()),
      task_run_count: flow.task_run_count ?? faker.datatype.number(10),
      updated: flow.updated ?? updated
    })
  }
}
