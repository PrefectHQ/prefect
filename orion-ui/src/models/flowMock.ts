import faker from 'faker'
import Flow, { IFlow } from './flow'
import { fakerRandomArray } from '@/utilities/faker'

export default class FlowMock extends Flow {
  constructor(flow: Partial<IFlow> = {}) {
    const id = flow.id ?? faker.datatype.uuid()
    const created = flow.created ?? faker.date.recent(7)
    const updated = flow.updated ?? faker.date.between(created, new Date())
    const name = flow.name ?? faker.lorem.slug(2)
    const tags = flow.tags ?? fakerRandomArray(5, () => faker.lorem.word())

    super({
      id,
      created,
      updated,
      name,
      tags
    })
  }
}
