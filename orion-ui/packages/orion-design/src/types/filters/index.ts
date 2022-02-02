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
  operation: 'after' | 'before',
  value: Date,
}

export type ObjectTimeFilter = {
  type: 'time',
  operation: 'newer' | 'older',
  value: `${number}h` | `${number}d` | `${number}w` | `${number}m` | `${number}y`,
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
export type FilterObjects = Filter['object']
export type FilterOperations = Required<Filter>['operation']
export type FilterTypes = Required<Filter>['type']
export type FilterValues = Required<Filter>['value']
export type ObjectFilter = Pick<Required<Filter>, 'type' | 'operation' | 'value'>

export * from './deployments'
export * from './flowRuns'
export * from './flows'
export * from './tags'
export * from './taskRuns'