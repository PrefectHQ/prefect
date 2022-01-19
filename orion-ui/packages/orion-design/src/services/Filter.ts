import { Filter, FlowFilter, FlowRunFilter, TaskRunFilter, DeploymentFilter, StateFilter, TimeFrameFilter } from '@/typings/filters'
import { BaseFilter, GlobalFilter, RunState, RunTimeFrame } from '@/typings/global'
import { isNonEmptyArray } from '@/utilities/arrays'
import { isSubState } from '@/utilities/states'
import { calculateEnd, calculateStart, isValidTimeFrame } from '@/utilities/timeFrame'

interface Sortable<T extends Filter> {
  sort?: [keyof T],
}

export type DeploymentsFilter = { deployments?: DeploymentFilter } & Sortable<DeploymentFilter>
export type FlowsFilter = { flows?: FlowFilter } & Sortable<FlowFilter>
export type TaskRunsFilter = { task_runs?: TaskRunFilter } & Sortable<TaskRunFilter>
export type FlowRunsFilter = { flow_runs?: FlowRunFilter } & Sortable<FlowRunFilter>

export type UnionFilters =
  & FlowsFilter
  & DeploymentsFilter
  & FlowRunsFilter
  & TaskRunsFilter

interface Historical {
  history_start: string,
  history_end: string,
  history_interval_seconds: number,
}

export type TaskRunsHistoryFilter = { task_runs?: TaskRunFilter } & Historical
export type FlowRunsHistoryFilter = { flow_runs?: FlowRunFilter } & Historical


function buildBaseFilter(baseFilter: BaseFilter): Filter {
  const filter: Filter = {}

  if (isNonEmptyArray(baseFilter.ids)) {
    filter.id = { any_: baseFilter.ids }
  }

  if (isNonEmptyArray(baseFilter.names)) {
    filter.name = { any_: baseFilter.names }
  }

  if (isNonEmptyArray(baseFilter.tags)) {
    filter.tags = { all_: baseFilter.tags }
  }

  return filter
}

function buildTimeFrameFilter(timeFrame: RunTimeFrame | undefined): TimeFrameFilter | undefined {
  if (timeFrame === undefined) {
    return timeFrame
  }

  let filter: TimeFrameFilter = {}

  if (isValidTimeFrame(timeFrame.from)) {
    filter = { ...filter, after_: calculateStart(timeFrame.from)!.toISOString() }
  }

  if (isValidTimeFrame(timeFrame.to)) {
    filter = { ...filter, before_: calculateEnd(timeFrame.to)!.toISOString() }
  }

  return filter
}

function buildStateFilter(states: RunState[] | undefined): StateFilter | undefined {
  if (states === undefined || !isNonEmptyArray(states)) {
    return states
  }

  let filter: StateFilter = {}

  const [stateNames, stateTypes] = states.reduce<[string[], string[]]>(([stateNames, stateTypes], state) => {
    if (isSubState(state.name)) {
      stateNames.push(state.name)
    } else {
      stateTypes.push(state.type)
    }

    return [stateNames, stateTypes]
  }, [[], []])

  if (stateNames.length > 0) {
    filter = { ...filter, name: { any_: stateNames } }
  }

  if (stateTypes.length > 0) {
    filter = { ...filter, type: { any_: stateTypes } }
  }

  return filter
}

function buildDeploymentFilter(globalFilter: GlobalFilter): DeploymentFilter {
  const filter: DeploymentFilter = buildBaseFilter(globalFilter.deployments)

  return filter
}

function buildFlowFilter(globalFilter: GlobalFilter): FlowFilter {
  const filter: FlowFilter = buildBaseFilter(globalFilter.flows)

  return filter
}

function buildFlowRunFilter(globalFilter: GlobalFilter): FlowRunFilter {
  const filter: FlowRunFilter = buildBaseFilter(globalFilter.flow_runs)

  filter.expected_start_time = buildTimeFrameFilter(globalFilter.flow_runs.timeframe)
  filter.state = buildStateFilter(globalFilter.flow_runs.states)

  return filter
}

function buildTaskRunFilter(globalFilter: GlobalFilter): TaskRunFilter {
  const filter: TaskRunFilter = buildBaseFilter(globalFilter.task_runs)

  filter.start_time = buildTimeFrameFilter(globalFilter.task_runs.timeframe)
  filter.state = buildStateFilter(globalFilter.task_runs.states)

  return filter
}

export function buildFilter(globalFilter: GlobalFilter): UnionFilters {
  const filters: UnionFilters = {}

  const deployments = buildDeploymentFilter(globalFilter)
  if (Object.keys(deployments).length > 0) {
    filters.deployments = deployments
  }

  const flows = buildFlowFilter(globalFilter)
  if (Object.keys(flows).length > 0) {
    filters.flows = flows
  }

  const flowRuns = buildFlowRunFilter(globalFilter)
  if (Object.keys(flowRuns).length > 0) {
    filters.flow_runs = flowRuns
  }

  const taskRuns = buildTaskRunFilter(globalFilter)
  if (Object.keys(taskRuns).length > 0) {
    filters.task_runs = taskRuns
  }

  return filters
}