/* eslint-disable import/no-duplicates */
import {
  FlowFilter as FlowFilterQuery,
  DeploymentFilter as DeploymentFilterQuery,
  FlowRunFilter as FlowRunFilterQuery,
  TaskRunFilter as TaskRunFilterQuery
} from '@/typings/filters'
import addDays from 'date-fns/addDays'
import addHours from 'date-fns/addHours'
import addMonths from 'date-fns/addMonths'
import addWeeks from 'date-fns/addWeeks'
import startOfToday from 'date-fns/startOfToday'
import { FilterRelativeDateUnitError } from '../models/FilterRelativeDateUnitError'
import { DeploymentFilter, Filter, FlowFilter, FlowRunFilter, RelativeDateFilterValue, TaskRunFilter } from '../types/filters'
import { isCompleteDeploymentFilter, isCompleteFlowFilter, isCompleteFlowRunFilter, isCompleteTaskRunFilter } from '../utilities/filters'
import { UnionFilters } from './Filter'

export class FiltersQueryService {

  public static query(filters: Required<Filter>[]): UnionFilters {
    const flowFilters = filters.filter(isCompleteFlowFilter)
    const flowRunFilters = filters.filter(isCompleteFlowRunFilter)
    const taskRunFilters = filters.filter(isCompleteTaskRunFilter)
    const deploymentFilters = filters.filter(isCompleteDeploymentFilter)

    const union: UnionFilters = {
      flows: this.createFlowFilter(flowFilters),
      // eslint-disable-next-line camelcase
      flow_runs: this.createFlowRunsFilter(flowRunFilters),
      // eslint-disable-next-line camelcase
      task_runs: this.createTaskRunsFilter(taskRunFilters),
      deployments: this.createDeploymentsFilter(deploymentFilters),
    }

    return union
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
              query.expected_start_time.after_ = this.createDateFromRelative(filter.value).toISOString()
              break
            case 'older':
              query.expected_start_time.before_ = this.createDateFromRelative(filter.value).toISOString()
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
              query.start_time.after_ = this.createDateFromRelative(filter.value).toISOString()
              break
            case 'older':
              query.start_time.before_ = this.createDateFromRelative(filter.value).toISOString()
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

  private static createDateFromRelative(relative: RelativeDateFilterValue): Date {
    const unit = relative.slice(-1)
    const value = parseInt(relative)
    const valueNegative = value * -1

    switch (unit) {
      case 'h':
        return addHours(new Date, valueNegative)
      case 'd':
        return addDays(startOfToday(), valueNegative)
      case 'w':
        return addWeeks(startOfToday(), valueNegative)
      case 'm':
        return addMonths(startOfToday(), valueNegative)
      default:
        throw new FilterRelativeDateUnitError()
    }

  }

}