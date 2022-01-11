import { ILogResponse } from '../services/LogsApi'

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
  sort?: `${Uppercase<keyof ILogResponse>}_${'ASC' | 'DSC'}`,
}