import { DeploymentFilter } from './deployments'
import { FlowRunFilter } from './flowRuns'
import { FlowFilter } from './flows'
import { TagFilter } from './tags'
import { TaskRunFilter } from './taskRuns'

export type ObjectStringFilter = {
  type: 'string',
  operation: 'contains' | 'equals',
  value: string,
}

export type ObjectDateFilter = {
  type: 'date',
  operation: 'after' | 'before' | 'older' | 'newer' | 'between',
  value: Date | Date[],
}

export type ObjectTagFilter = {
  type: 'tag',
  operation: 'and',
  value: string[],
}

export type ObjectStateFilter = {
  type: 'state',
  operation: 'or',
  value: string[],
}

export type ObjectNumberFilter = {
  type: 'number',
  operation: 'less' | 'more',
  value: number,
}

export type Filter = FlowFilter | DeploymentFilter | FlowRunFilter | TaskRunFilter | TagFilter
export type FilterEntities = Filter['object']
export type FilterOperations = Filter['operation']
export type FilterTypes = Filter['type']
export type FilterValues = Filter['value']
export type ObjectFilter = Pick<Filter, 'type' | 'operation' | 'value'>

export * from './deployments'
export * from './flowRuns'
export * from './flows'
export * from './tags'
export * from './taskRuns'