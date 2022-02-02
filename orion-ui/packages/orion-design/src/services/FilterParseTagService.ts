/* eslint-disable default-case */
import { isCompleteFilter } from '..'
import { DeploymentFilter, Filter, FilterObject, FilterOperation, FilterProperty, FilterType, FilterValue, FlowFilter, FlowRunFilter, ObjectTagPrefixDictionary, ObjectTagPrefixes, TagFilter, TagPrefixObjectDictionary, TaskRunFilter } from '../types'


export class FilterParseTagService {
  public convertTagsToFilters(tags: string[]): Required<Filter | null>[] {
    return tags.map(tag => this.convertTagToFilter(tag))
  }

  // null shouldn't be necessary
  public convertTagToFilter(tag: string): Required<Filter> | null {
    const filter: Filter = {
      object: this.parseObject(tag),
    }

    filter.property = this.parseProperty(filter.object, tag)
    filter.type = this.parseType(filter.object, filter.property, tag)

    if (!isCompleteFilter(filter)) {
      return null
    }

    return filter
  }

  private parseObject(tag: string): FilterObject {
    const prefix = ObjectTagPrefixes.find(prefix => tag.startsWith(prefix))

    if (prefix === undefined) {
      throw 'tag does not start with a valid prefix'
    }

    return TagPrefixObjectDictionary[prefix]
  }

  private parseProperty(object: FilterObject, tag: string): FilterProperty {
    const prefix = ObjectTagPrefixDictionary[object]
    const regex = new RegExp(`${prefix}(.*):.*`)
    const match = tag.match(regex)

    if (match === null) {
      throw 'tag does not contain a suffix'
    }

    // can suffix be type safe?
    const [, suffix] = match

    switch (object) {
      case 'flow':
        return this.getFlowPropertyFromSuffix(suffix)
      case 'deployment':
        return this.getDeploymentPropertyFromSuffix(suffix)
      case 'flow_run':
        return this.getFlowRunPropertyFromSuffix(suffix)
      case 'task_run':
        return this.getTaskRunPropertyFromSuffix(suffix)
      case 'tag':
        return this.getTagPropertyFromSuffix(suffix)
    }
  }

  private isFlowObject(object: FilterObject): object is 'flow' {
    return object === 'flow'
  }

  // type test = Extract<Required<Filter>, { object: 'flow' }>['property']
  private parseType<T extends FilterObject, P extends Extract<Required<Filter>, { object: T }>['property']>(object: T, property: P): FilterType {
    switch (object) {
      case 'flow':
        return this.getFlowTypeFromProperty(property)
      case 'deployment':
        return this.getDeploymentTypeFromProperty(property)
      case 'flow_run':
        return this.getFlowRunTypeFromProperty(property)
      case 'task_run':
        return this.getTaskRunTypeFromProperty(property)
      case 'tag':
        return this.getTagTypeFromProperty(property)
    }

  }

  private parseOperation(tag: string): FilterOperation {

  }

  private parseValue(tag: string): FilterValue {

  }

  private getDeploymentPropertyFromSuffix(suffix: string): Required<DeploymentFilter>['property'] {
    switch (suffix) {
      case '':
        return 'name'
      case 't':
        return 'tag'
      default:
        throw 'deployment filter not have a valid suffix'
    }
  }

  private getFlowPropertyFromSuffix(suffix: string): Required<FlowFilter>['property'] {
    switch (suffix) {
      case '':
        return 'name'
      case 't':
        return 'tag'
      default:
        throw 'flow filter not have a valid suffix'
    }
  }

  private getFlowRunPropertyFromSuffix(suffix: string): Required<FlowRunFilter>['property'] {
    switch (suffix) {
      case '':
        return 'name'
      case 't':
        return 'tag'
      case 's':
        return 'state'
      case 'ra':
      case 'rb':
      case 'rn':
      case 'ro':
        return 'start_date'
      default:
        throw 'flow run tag does not have a valid suffix'
    }
  }

  private getTaskRunPropertyFromSuffix(suffix: string): Required<TaskRunFilter>['property'] {
    switch (suffix) {
      case '':
        return 'name'
      case 't':
        return 'tag'
      case 's':
        return 'state'
      case 'ra':
      case 'rb':
      case 'rn':
      case 'ro':
        return 'start_date'
      default:
        throw 'task run filter not have a valid suffix'
    }
  }

  private getTagPropertyFromSuffix(suffix: string): Required<TagFilter>['property'] {
    switch (suffix) {
      case '':
        return 'name'
      default:
        throw 'tag filter not have a valid suffix'
    }
  }

  private getDeploymentTypeFromProperty(property: Required<DeploymentFilter>['property']): Required<DeploymentFilter>['type'] {
    switch (property) {
      case 'tag':
        return 'tag'
      case 'name':
        return 'string'
    }
  }

  private getFlowTypeFromProperty(property: Required<FlowFilter>['property']): Required<FlowFilter>['type'] {
    switch (property) {
      case 'tag':
        return 'tag'
      case 'name':
        return 'string'
    }
  }

  private getFlowRunTypeFromProperty(property: Required<FlowRunFilter>['property']): Required<FlowRunFilter>['type'] {
    switch (property) {
      case 'tag':
        return 'tag'
      case 'name':
        return 'string'
      case 'start_date':
        return 'date' // or time
      case 'state':
        return 'state'
    }
  }

  private getTaskRunTypeFromProperty(property: Required<TaskRunFilter>['property']): Required<TaskRunFilter>['type'] {
    switch (property) {
      case 'tag':
        return 'tag'
      case 'name':
        return 'string'
      case 'start_date':
        return 'date' // or time
      case 'state':
        return 'state'
    }
  }

  private getTagTypeFromProperty(property: Required<TagFilter>['property']): Required<TagFilter>['type'] {
    switch (property) {
      case 'name':
        return 'string'
    }
  }

}