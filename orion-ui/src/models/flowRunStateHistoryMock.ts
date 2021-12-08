/* eslint-disable @typescript-eslint/no-non-null-assertion */

import FlowRunStateHistory, {
  IFlowRunStateHistory
} from './flowRunStateHistory'
import { StateNames } from '@/types/states'
import { fakerRandomState } from '@/utilities/faker'
import faker from 'faker'

export default class FlowRunStateHistoryMock extends FlowRunStateHistory {
  constructor(state: Partial<IFlowRunStateHistory> = {}) {
    const state_type = state.state_type ?? fakerRandomState()
    const state_name = state.state_name ?? StateNames.get(state_type)!
    const count_runs = state.count_runs ?? faker.datatype.number(100)
    const sum_estimated_run_time =
      state.sum_estimated_run_time ?? faker.datatype.number(100)
    const sum_estimated_lateness =
      state.sum_estimated_lateness ?? faker.datatype.number(100)

    super({
      state_type,
      state_name,
      count_runs,
      sum_estimated_run_time,
      sum_estimated_lateness
    })
  }
}
