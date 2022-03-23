import { ILogResponse } from '@/models/ILogResponse'

export type LogsRequestSort = `${Uppercase<keyof ILogResponse>}_${'ASC' | 'DSC'}`

export interface LogsRequestFilter {
  limit?: number,
  offset?: number,
  logs?: {
    level?: {
      ge_?: number,
      le_?: number,
    },
    timestamp?: {
      before_?: string,
      after_?: string,
    },
    flow_run_id?: {
      any_?: string[],
    },
    task_run_id?: {
      any_?: string[],
    },
  },
  sort?: LogsRequestSort,
}