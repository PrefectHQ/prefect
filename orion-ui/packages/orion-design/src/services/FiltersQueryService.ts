import {
  FlowFilter as FlowFilterQuery,
  DeploymentFilter as DeploymentFilterQuery,
  FlowRunFilter as FlowRunFilterQuery,
  TaskRunFilter as TaskRunFilterQuery
} from '@/typings/filters'
import { DeploymentFilter, Filter, FlowFilter, FlowRunFilter, TaskRunFilter } from '../types/filters'
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
        case 'start_date': { throw new Error('Not implemented yet: "start_date" case') }
        case 'state': { throw new Error('Not implemented yet: "state" case') }
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
        case 'start_date': { throw new Error('Not implemented yet: "start_date" case') }
        case 'state': { throw new Error('Not implemented yet: "state" case') }
      }
    })

    return query
  }

}