import { ILogResponse } from '@/models/ILogResponse'
import { Log } from '@/models/Log'
import { MapFunction } from '@/services/Mapper'

export const mapILogResponseToLog: MapFunction<ILogResponse, Log> = function(source: ILogResponse): Log {
  return new Log({
    id: source.id,
    created: this.map('string', source.created, 'Date'),
    updated: this.map('string', source.updated, 'Date'),
    name: source.name,
    level: source.level,
    message: source.message,
    timestamp: this.map('string', source.timestamp, 'Date'),
    flowRunId: source.flow_run_id,
    taskRunId: source.task_run_id,
  })
}

export const mapLogToILogResponse: MapFunction<Log, ILogResponse> = function(source: Log): ILogResponse {
  return {
    'id': source.id,
    'created': this.map('Date', source.created, 'string'),
    'updated': this.map('Date', source.updated, 'string'),
    'name': source.name,
    'level': source.level,
    'message': source.message,
    'timestamp': this.map('Date', source.timestamp, 'string'),
    'flow_run_id': source.flowRunId,
    'task_run_id': source.taskRunId,
  }
}