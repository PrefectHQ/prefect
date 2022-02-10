import {
  Filter,
  FlowFilter,
  DeploymentFilter,
  FlowRunFilter,
  TaskRunFilter,
  TagFilter,
  FlowStringFilter,
  FlowTagFilter,
  DeploymentStringFilter,
  DeploymentTagFilter,
  FlowRunStringFilter,
  FlowRunStateFilter,
  FlowRunDateFilter,
  FlowRunTagFilter,
  TaskRunStringFilter,
  TaskRunStateFilter,
  TaskRunDateFilter,
  TaskRunTagFilter,
  ObjectFilter,
  ObjectStringFilter,
  ObjectDateFilter,
  ObjectStateFilter,
  ObjectTagFilter
} from '../types/filters'

export function isCompleteFilter(filter: Partial<Filter>): filter is Required<Filter> {
  return !!(filter.operation && filter.property && filter.type && filter.value)
}

export function isFilter(filter: Partial<Filter>): filter is Filter {
  return filter.object !== undefined
}

export function isFlowFilter(filter: Filter): filter is FlowFilter {
  return filter.object == 'flow'
}

export function isDeploymentFilter(filter: Filter): filter is DeploymentFilter {
  return filter.object === 'deployment'
}

export function isFlowRunFilter(filter: Filter): filter is FlowRunFilter {
  return filter.object === 'flow_run'
}

export function isTaskRunFilter(filter: Filter): filter is TaskRunFilter {
  return filter.object === 'task_run'
}

export function isTagFilter(filter: Filter): filter is TagFilter {
  return filter.object === 'tag'
}

export function isFlowStringFilter(filter: Filter): filter is FlowStringFilter {
  return isFlowFilter(filter) && filter.type === 'string'
}

export function isFlowTagFilter(filter: Filter): filter is FlowTagFilter {
  return isFlowFilter(filter) && filter.type === 'tag'
}

export function isDeploymentStringFilter(filter: Filter): filter is DeploymentStringFilter {
  return isDeploymentFilter(filter) && filter.type === 'string'
}

export function isDeploymentTagFilter(filter: Filter): filter is DeploymentTagFilter {
  return isDeploymentFilter(filter) && filter.type === 'tag'
}

export function isFlowRunStringFilter(filter: Filter): filter is FlowRunStringFilter {
  return isFlowRunFilter(filter) && filter.type === 'string'
}

export function isFlowRunStateFilter(filter: Filter): filter is FlowRunStateFilter {
  return isFlowRunFilter(filter) && filter.type === 'state'
}

export function isFlowRunDateFilter(filter: Filter): filter is FlowRunDateFilter {
  return isFlowRunFilter(filter) && filter.type === 'date'
}

export function isFlowRunTagFilter(filter: Filter): filter is FlowRunTagFilter {
  return isFlowRunFilter(filter) && filter.type === 'tag'
}

export function isTaskRunStringFilter(filter: Filter): filter is TaskRunStringFilter {
  return isTaskRunFilter(filter) && filter.type === 'string'
}

export function isTaskRunStateFilter(filter: Filter): filter is TaskRunStateFilter {
  return isTaskRunFilter(filter) && filter.type === 'state'
}

export function isTaskRunDateFilter(filter: Filter): filter is TaskRunDateFilter {
  return isTaskRunFilter(filter) && filter.type === 'date'
}

export function isTaskRunTagFilter(filter: Filter): filter is TaskRunTagFilter {
  return isTaskRunFilter(filter) && filter.type === 'tag'
}

export function isObjectStringFilter(filter: ObjectFilter): filter is ObjectStringFilter {
  return filter.type == 'string'
}

export function isObjectDateFilter(filter: ObjectFilter): filter is ObjectDateFilter {
  return filter.type == 'date'
}

export function isObjectStateFilter(filter: ObjectFilter): filter is ObjectStateFilter {
  return filter.type == 'state'
}

export function isObjectTagFilter(filter: ObjectFilter): filter is ObjectTagFilter {
  return filter.type == 'tag'
}