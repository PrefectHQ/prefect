import { ILogResponse } from '@/models/ILogResponse'
import { Log } from '@/models/Log'
import { Profile } from '@/services/Translate'

export const logsProfile: Profile<ILogResponse, Log> = {
  toDestination(source) {
    return new Log({
      id: source.id,
      created: new Date(source.created),
      updated: new Date(source.updated),
      name: source.name,
      level: source.level,
      message: source.message,
      timestamp: new Date(source.timestamp),
      flowRunId: source.flow_run_id,
      taskRunId: source.task_run_id,
    })
  },
  toSource(destination) {
    return {
      'id': destination.id,
      'created': destination.created.toISOString(),
      'updated': destination.updated.toISOString(),
      'name': destination.name,
      'level': destination.level,
      'message': destination.message,
      'timestamp': destination.timestamp.toISOString(),
      'flow_run_id': destination.flowRunId,
      'task_run_id': destination.taskRunId,
    }
  },
}