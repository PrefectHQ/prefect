/* eslint-disable default-case */
import {
  Filter,
  FilterTagPrefix,
  ObjectDateFilter,
  ObjectStateFilter,
  ObjectStringFilter,
  ObjectTagFilter,
  ObjectTagPrefixDictionary,
  ObjectTimeFilter
} from '../types/filters'
import { formatDateTimeNumeric } from '../utilities/dates'

export class FilterStringifyService {
  public convertFiltersToTags(filters: Required<Filter>[]): string[] {
    return filters.map(filter => this.convertFilterToTag(filter))
  }

  public convertFilterToTag(filter: Required<Filter>): string {
    const tagPrefix = this.createTagPrefix(filter)
    const tagSuffix = this.createTagSuffix(filter)
    const tagValue = this.createTagValue(filter)

    return `${tagPrefix}${tagSuffix}:${tagValue}`
  }

  private createObjectStringFilterValue(filter: ObjectStringFilter): string {
    switch (filter.operation) {
      case 'contains':
        return filter.value
      case 'equals':
        return `"${filter.value}"`
    }
  }

  private createObjectDateFilterValue(filter: ObjectDateFilter): string {
    return formatDateTimeNumeric(filter.value)
  }

  private createObjectTimeFilterValue(filter: ObjectTimeFilter): string {
    return filter.value
  }

  private createObjectStateFilterValue(filter: ObjectStateFilter): string {
    return filter.value.join('|')
  }

  private createObjectTagFilterValue(filter: ObjectTagFilter): string {
    return filter.value.join(',')
  }

  private createTagPrefix(filter: Required<Filter>): FilterTagPrefix {
    return ObjectTagPrefixDictionary[filter.object]
  }

  private createTagSuffix(filter: Required<Filter>): string {
    switch (filter.type) {
      case 'string':
        return ''
      case 'state':
      case 'tag':
        return filter.type[0]
      case 'date':
      case 'time':
        return filter.operation[0]
    }
  }

  private createTagValue(filter: Required<Filter>): string {
    switch (filter.type) {
      case 'string':
        return this.createObjectStringFilterValue(filter)
      case 'state':
        return this.createObjectStateFilterValue(filter)
      case 'tag':
        return this.createObjectTagFilterValue(filter)
      case 'date':
        return this.createObjectDateFilterValue(filter)
      case 'time':
        return this.createObjectTimeFilterValue(filter)
    }
  }

}