import { DeploymentFilter } from './deployments'
import { FlowRunFilter } from './flowRuns'
import { FlowFilter } from './flows'
import { TagFilter } from './tags'
import { TaskRunFilter } from './taskRuns'

export type EntityStringFilter = {
  type: 'string',
  operation: 'contains' | 'equals',
  value: string,
}

export type EntityDateFilter = {
  type: 'date',
  operation: 'after' | 'before' | 'older' | 'newer' | 'between',
  value: Date | Date[],
}

export type EntityTagFilter = {
  type: 'tag',
  operation: 'and',
  value: string[],
}

export type EntityStateFilter = {
  type: 'state',
  operation: 'or',
  value: string[],
}

export type EntityNumberFilter = {
  type: 'number',
  operation: 'less' | 'more',
  value: number,
}

export type Filter = FlowFilter | DeploymentFilter | FlowRunFilter | TaskRunFilter | TagFilter

export type FilterEntities = Filter['entity']
export type FilterOperations = Filter['operation']
export type FilterTypes = Filter['type']
export type FilterValues = Filter['value']
export type EntityFilter = Pick<Filter, 'type' | 'operation' | 'value'>

export * from './deployments'
export * from './flowRuns'
export * from './flows'
export * from './tags'
export * from './taskRuns'