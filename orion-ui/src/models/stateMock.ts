/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { StateNames } from '@prefecthq/orion-design'
import faker from 'faker'
import State, { IState } from './state'
import { fakerRandomState } from '@/utilities/faker'

export default class StateMock extends State {
  constructor(state: Partial<IState> = {}) {
    const id = state.id ?? faker.datatype.uuid()
    const type = state.type ?? fakerRandomState()
    const name = state.name ?? StateNames.get(type)!
    const message =
      state.message ??
      faker.lorem.word(faker.datatype.number({ min: 1, max: 20 }))

    const state_details = state.state_details ?? {}
    const data = state.data ?? {}
    const timestamp = state.timestamp ?? faker.date.recent(7).toString()

    super({
      id,
      type,
      name,
      message,
      state_details,
      data,
      timestamp,
    })
  }
}
