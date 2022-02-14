/* eslint-disable default-case */
import {
  Filter,
  FilterTagPrefix,
  ObjectDateFilter,
  ObjectStateFilter,
  ObjectStringFilter,
  ObjectTagFilter,
  ObjectTagPrefixDictionary,
  ObjectRelativeDateFilter
} from '../types/filters'
import { formatDateTimeNumeric } from '../utilities/dates'

export class FilterStringifyService {
  public static convertFiltersToTags(filters: Required<Filter>[]): string[] {
    return filters.map(filter => this.convertFilterToTag(filter))
  }

  public static convertFilterToTag(filter: Required<Filter>): string {
    const tagPrefix = this.createTagPrefix(filter)
    const tagSuffix = this.createTagSuffix(filter)
    const tagValue = this.createTagValue(filter)

    return `${tagPrefix}${tagSuffix}:${tagValue}`
  }

  private static createObjectStringFilterValue(filter: ObjectStringFilter): string {
    switch (filter.operation) {
      case 'contains':
        return filter.value
      case 'equals':
        return `"${filter.value}"`
    }
  }

  private static createObjectDateFilterValue(filter: ObjectDateFilter | ObjectRelativeDateFilter): string {
    switch (filter.operation) {
      case 'after':
      case 'before':
        return formatDateTimeNumeric(filter.value)
      case 'newer':
      case 'older':
      case 'upcoming':
        return filter.value
    }
  }

  private static createObjectStateFilterValue(filter: ObjectStateFilter): string {
    return filter.value.join('|')
  }

  private static createObjectTagFilterValue(filter: ObjectTagFilter): string {
    return filter.value.join(',')
  }

  private static createTagPrefix(filter: Required<Filter>): FilterTagPrefix {
    return ObjectTagPrefixDictionary[filter.object]
  }

  private static createTagSuffix(filter: Required<Filter>): string {
    switch (filter.type) {
      case 'string':
        return ''
      case 'state':
      case 'tag':
        return filter.type[0]
      case 'date':
        return filter.operation[0]
    }
  }

  private static createTagValue(filter: Required<Filter>): string {
    switch (filter.type) {
      case 'string':
        return this.createObjectStringFilterValue(filter)
      case 'state':
        return this.createObjectStateFilterValue(filter)
      case 'tag':
        return this.createObjectTagFilterValue(filter)
      case 'date':
        return this.createObjectDateFilterValue(filter)
    }
  }

}