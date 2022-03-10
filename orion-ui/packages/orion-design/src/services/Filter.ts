import { Filter, FlowFilter, FlowRunFilter, TaskRunFilter, DeploymentFilter } from '@/types/filters/server-types'

export type PaginatedFilter = {
  limit?: number,
  offset?: number,
}

type StringKeys<T extends Filter> = Extract<keyof T, string>
type Sortable<T extends Filter> = PaginatedFilter & {
  sort?: `${Uppercase<StringKeys<T>>}_${'ASC' | 'DESC'}`,
}

export type DeploymentsFilter = { deployments?: DeploymentFilter }
export type FlowsFilter = { flows?: FlowFilter }
export type TaskRunsFilter = { task_runs?: TaskRunFilter }
export type FlowRunsFilter = { flow_runs?: FlowRunFilter }

export type UnionFilters =
  & FlowsFilter
  & DeploymentsFilter
  & FlowRunsFilter
  & TaskRunsFilter
  & Sortable<FlowFilter & DeploymentFilter & TaskRunFilter & FlowRunFilter>

interface Historical {
  history_start: string,
  history_end: string,
  history_interval_seconds: number,
}

export type TaskRunsHistoryFilter = { task_runs?: TaskRunFilter } & Historical
export type FlowRunsHistoryFilter = { flow_runs?: FlowRunFilter } & Historical