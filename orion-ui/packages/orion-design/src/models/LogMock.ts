import faker from 'faker'
import { Log, ILog } from './Log'

export class LogMock extends Log {
  public constructor(log: Partial<ILog> = {}) {
    const id = log.id ?? faker.datatype.uuid()
    const created = log.created ?? faker.date.recent(7)
    const updated = log.updated ?? created
    const name = log.name ?? faker.lorem.slug(2)
    const level = log.level ?? faker.datatype.number(1)
    const message = log.message ?? faker.lorem.sentences(1)
    const timestamp = log.timestamp ?? created
    const flowRunId = log.flowRunId ?? faker.datatype.uuid()
    const taskRunId = log.taskRunId ?? faker.datatype.uuid()

    super({
      id,
      created,
      updated,
      name,
      level,
      message,
      timestamp,
      flowRunId,
      taskRunId,
    })
  }
}
