/* eslint-disable import/no-duplicates */
import addDays from 'date-fns/addDays'
import addHours from 'date-fns/addHours'
import addMonths from 'date-fns/addMonths'
import addWeeks from 'date-fns/addWeeks'
import startOfToday from 'date-fns/startOfToday'
import subDays from 'date-fns/subDays'
import { FilterRelativeDateUnitError } from '@/models/FilterRelativeDateUnitError'
import { FlowRunsHistoryFilter, UnionFilters } from '@/services/Filter'
import { DeploymentFilter, Filter, FlowFilter, FlowRunFilter, RelativeDateFilterValue, TaskRunFilter } from '@/types/filters'
import { isCompleteDeploymentFilter, isCompleteFlowFilter, isCompleteFlowRunFilter, isCompleteTaskRunFilter } from '@/utilities/filters'

export class FiltersQueryService {

  public static query(filters: Required<Filter>[]): UnionFilters {
    const union: UnionFilters = {}

    const flowFilters = filters.filter(isCompleteFlowFilter)

    if (flowFilters.length) {
      union.flows = this.createFlowFilter(flowFilters)
    }

    const flowRunFilters = filters.filter(isCompleteFlowRunFilter)

    if (flowRunFilters.length) {
      // eslint-disable-next-line camelcase
      union.flow_runs = this.createFlowRunsFilter(flowRunFilters)
    }

    const taskRunFilters = filters.filter(isCompleteTaskRunFilter)

    if (taskRunFilters.length) {
      // eslint-disable-next-line camelcase
      union.task_runs = this.createTaskRunsFilter(taskRunFilters)
    }

    const deploymentFilters = filters.filter(isCompleteDeploymentFilter)

    if (deploymentFilters.length) {
      union.deployments = this.createDeploymentsFilter(deploymentFilters)
    }

    return union
  }

  public static flowHistoryQuery(filters: Required<Filter>[], defaultHistoryStart?: Date, defaultHistoryEnd?: Date): FlowRunsHistoryFilter {
    const query = this.query(filters)
    const queryEnd = query.flow_runs?.expected_start_time?.before_
    const queryStart = query.flow_runs?.expected_start_time?.after_

    // eslint-disable-next-line no-nested-ternary
    const historyEnd = queryEnd ? new Date(queryEnd) : defaultHistoryEnd ? defaultHistoryEnd : addHours(new Date(), 1)
    // eslint-disable-next-line no-nested-ternary
    const historyStart = queryStart ? new Date(queryStart) : defaultHistoryStart ? defaultHistoryStart : subDays(historyEnd, 7)
    const interval = this.createIntervalSeconds(historyStart, historyEnd)

    return {
      // eslint-disable-next-line camelcase
      history_end: historyEnd.toISOString(),
      // eslint-disable-next-line camelcase
      history_start: historyStart.toISOString(),
      // eslint-disable-next-line camelcase
      history_interval_seconds: interval,
      ...query,
    }
  }

  private static createFlowFilter(filters: Required<FlowFilter>[]): FlowFilterQuery {
    const query: FlowFilterQuery = {}

    filters.forEach(filter => {
      switch (filter.property) {
        case 'name':
          query.name ??= { any_: [] }
          query.name.any_?.push(filter.value)
          break
        case 'tag':
          query.tags ??= { all_: [] }
          query.tags.all_?.push(...filter.value)
      }
    })

    return query
  }

  private static createDeploymentsFilter(filters: Required<DeploymentFilter>[]): DeploymentFilterQuery {
    const query: DeploymentFilterQuery = {}

    filters.forEach(filter => {
      switch (filter.property) {
        case 'name':
          query.name ??= { any_: [] }
          query.name.any_?.push(filter.value)
          break
        case 'tag':
          query.tags ??= { all_: [] }
          query.tags.all_?.push(...filter.value)
          break
      }
    })

    return query
  }

  private static createFlowRunsFilter(filters: Required<FlowRunFilter>[]): FlowRunFilterQuery {
    const query: FlowRunFilterQuery = {}

    filters.forEach(filter => {
      switch (filter.property) {
        case 'name':
          query.name ??= { any_: [] }
          query.name.any_?.push(filter.value)
          break
        case 'tag':
          query.tags ??= { all_: [] }
          query.tags.all_?.push(...filter.value)
          break
        case 'start_date':
          // eslint-disable-next-line camelcase
          query.expected_start_time ??= {}

          switch (filter.operation) {
            case 'after':
              query.expected_start_time.after_ = filter.value.toISOString()
              break
            case 'before':
              query.expected_start_time.before_ = filter.value.toISOString()
              break
            case 'newer':
              query.expected_start_time.after_ = this.createRelativeDate(filter.value).toISOString()
              break
            case 'older':
              query.expected_start_time.before_ = this.createRelativeDate(filter.value).toISOString()
              break
            case 'upcoming':
              query.expected_start_time.before_ = this.createUpcomingRelativeDate(filter.value).toISOString()
          }

          break
        case 'state':
          query.state ??= { type: { any_: [] } }
          query.state.type?.any_?.push(...filter.value)
          break
      }
    })

    return query
  }

  private static createTaskRunsFilter(filters: Required<TaskRunFilter>[]): TaskRunFilterQuery {
    const query: TaskRunFilterQuery = {}

    filters.forEach(filter => {
      switch (filter.property) {
        case 'name':
          query.name ??= { any_: [] }
          query.name.any_?.push(filter.value)
          break
        case 'tag':
          query.tags ??= { all_: [] }
          query.tags.all_?.push(...filter.value)
          break
        case 'start_date':
          // eslint-disable-next-line camelcase
          query.start_time ??= {}

          switch (filter.operation) {
            case 'after':
              query.start_time.after_ = filter.value.toISOString()
              break
            case 'before':
              query.start_time.before_ = filter.value.toISOString()
              break
            case 'newer':
              query.start_time.after_ = this.createRelativeDate(filter.value).toISOString()
              break
            case 'older':
              query.start_time.before_ = this.createRelativeDate(filter.value).toISOString()
              break
          }

          break
        case 'state':
          query.state ??= { type: { any_: [] } }
          query.state.type?.any_?.push(...filter.value)
          break
      }
    })

    return query
  }

  private static createRelativeDate(relative: RelativeDateFilterValue): Date {
    const unit = relative.slice(-1)
    const value = parseInt(relative)
    const valueNegative = value * -1

    return this.createDateFromUnitAndValue(unit, valueNegative)

  }

  private static createUpcomingRelativeDate(relative: RelativeDateFilterValue): Date {
    const unit = relative.slice(-1)
    const value = parseInt(relative)

    return this.createDateFromUnitAndValue(unit, value)
  }

  private static createDateFromUnitAndValue(unit: string, value: number): Date {
    switch (unit) {
      case 'h':
        return addHours(new Date, value)
      case 'd':
        return addDays(startOfToday(), value)
      case 'w':
        return addWeeks(startOfToday(), value)
      case 'm':
        return addMonths(startOfToday(), value)
      default:
        throw new FilterRelativeDateUnitError()
    }

  }

  private static createIntervalSeconds(start: Date, end: Date): number {
    const seconds = (end.getTime() - start.getTime()) / 1000
    const defaultInterval = 60

    return Math.floor(seconds / 30) || defaultInterval
  }

}