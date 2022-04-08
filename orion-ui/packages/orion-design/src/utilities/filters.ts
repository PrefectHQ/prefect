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
  ObjectStringFilter,
  ObjectDateFilter,
  ObjectStateFilter,
  ObjectTagFilter,
  FilterOperation
} from '@/types/filters'

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

export function isCompleteFilter(filter: Partial<Filter>): filter is Required<Filter> {
  // the types aren't technically correct for this. Would love to use a NonEmptyArray type here
  if (Array.isArray(filter.value) && filter.value.length === 0) {
    return false
  }

  return !!(filter.operation && filter.property && filter.type && filter.value)
}

export function isCompleteFlowFilter(filter: Filter): filter is Required<FlowFilter> {
  return isFlowFilter(filter) && isCompleteFilter(filter)
}

export function isCompleteDeploymentFilter(filter: Filter): filter is Required<DeploymentFilter> {
  return isDeploymentFilter(filter) && isCompleteFilter(filter)
}

export function isCompleteFlowRunFilter(filter: Filter): filter is Required<FlowRunFilter> {
  return isFlowRunFilter(filter) && isCompleteFilter(filter)
}

export function isCompleteTaskRunFilter(filter: Filter): filter is Required<TaskRunFilter> {
  return isTaskRunFilter(filter) && isCompleteFilter(filter)
}

export function isCompleteTagFilter(filter: Filter): filter is Required<TagFilter> {
  return isTagFilter(filter) && isCompleteFilter(filter)
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

export function isObjectStringFilter(filter: Filter): filter is Filter & ObjectStringFilter {
  return filter.type == 'string'
}

export function isObjectDateFilter(filter: Filter): filter is Filter & ObjectDateFilter {
  return filter.type == 'date'
}

export function isObjectStateFilter(filter: Filter): filter is Filter & ObjectStateFilter {
  return filter.type == 'state'
}

export function isObjectTagFilter(filter: Filter): filter is Filter & ObjectTagFilter {
  return filter.type == 'tag'
}

export function hasFilter(haystack: Filter[], needle: Filter): boolean {
  return haystack.some((filter: Filter) => {
    if (filter.object != needle.object || filter.property != needle.property || filter.operation != needle.operation) {
      return false
    }

    if (Array.isArray(filter.value) && Array.isArray(needle.value)) {
      return filter.value.some(value => (needle.value as unknown[]).includes(value))
    }

    return filter.value == needle.value
  })
}

export function isRelativeDateOperation(value: FilterOperation): value is 'newer' | 'older' | 'upcoming' {
  return ['newer', 'older', 'upcoming'].includes(value)
}

export function isDateOperation(value: FilterOperation): value is 'after' | 'before' {
  return ['after', 'before'].includes(value)
}