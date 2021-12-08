/* eslint-disable @typescript-eslint/no-non-null-assertion */
import FlowRunHistory, { IFlowRunHistory } from './flowRunHistory'
import FlowRunStateHistoryMock from './flowRunStateHistoryMock'
import faker from 'faker'
import { fakerRandomArray } from '@/utilities/faker'
import { State, StateNames, States } from '@/types/states'

export default class FlowRunHistoryMock extends FlowRunHistory {
  constructor(flow: Partial<IFlowRunHistory> = {}) {
    const interval_start = flow.interval_start ?? faker.date.recent(7)
    const interval_end =
      flow.interval_end ?? faker.date.between(interval_start, new Date())
    const possibleStates: State[] = Object.values(States)

    super({
      interval_start,
      interval_end,
      states:
        flow.states ??
        fakerRandomArray(possibleStates.length, () => {
          const index = faker.datatype.number(possibleStates.length - 1)
          const state_type = possibleStates.splice(index, 1)[0]
          const state_name = StateNames.get(state_type)!

          return new FlowRunStateHistoryMock({
            state_type,
            state_name,
            count_runs: faker.datatype.number(20),
            sum_estimated_run_time: faker.datatype.number(20),
            sum_estimated_lateness: faker.datatype.number(20)
          })
        })
    })
  }
}
