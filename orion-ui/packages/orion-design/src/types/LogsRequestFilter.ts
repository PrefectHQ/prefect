import { ILogResponse } from '../services/LogsApi'
import { RequestFilter } from '.'

export interface LogsRequestFilter extends RequestFilter {
  sort: `${Uppercase<keyof ILogResponse>}_${'ASC' | 'DSC'}`,
}