import {
  Filter,
  ObjectDateFilter,
  ObjectStateFilter,
  ObjectStringFilter,
  ObjectTagFilter,
  ObjectRelativeDateFilter,
  ObjectUpcomingRelativeDateFilter,
  ObjectTagPrefixDictionary
} from '@/types/filters'
import { formatDateTimeNumericInTimeZone } from '@/utilities/dates'

export type FilterStringifyMethod = 'short' | 'full'
export type FilterStringifyOptions = { method?: FilterStringifyMethod }

export class FilterStringifyService {
  public static stringifyFilters(filters: Required<Filter>[], options?: FilterStringifyOptions): string[] {
    return filters.map(filter => this.stringifyFilter(filter, options))
  }

  public static stringifyFilter(filter: Required<Filter>, { method = 'full' }: FilterStringifyOptions = {}): string {
    const short = method === 'short'
    const tag = short ? this.createTagShort(filter) : this.createTag(filter)
    const value = this.createTagValue(filter)

    return `${tag}:${value}`
  }

  private static createObjectStringFilterValue(filter: ObjectStringFilter): string {
    switch (filter.operation) {
      case 'contains':
        return filter.value
      case 'equals':
        return `"${filter.value}"`
    }
  }

  private static createObjectDateFilterValue(filter: ObjectDateFilter | ObjectRelativeDateFilter | ObjectUpcomingRelativeDateFilter): string {
    switch (filter.operation) {
      case 'after':
      case 'before':
        return formatDateTimeNumericInTimeZone(filter.value)
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

  private static createTag(filter: Required<Filter>): string {
    const prefix = this.createTagPrefix(filter)
    const suffix = this.createTagSuffix(filter)

    if (suffix.length) {
      return `${prefix}_${suffix}`
    }

    return prefix
  }

  private static createTagShort(filter: Required<Filter>): string {
    const prefix = this.createTagPrefixShort(filter)
    const suffix = this.createTagSuffixShort(filter)

    return `${prefix}${suffix}`
  }

  private static createTagPrefix(filter: Required<Filter>): string {
    return filter.object
  }

  private static createTagPrefixShort(filter: Required<Filter>): string {
    return ObjectTagPrefixDictionary[filter.object]
  }

  private static createTagSuffix(filter: Required<Filter>): string {
    switch (filter.type) {
      case 'string':
        return ''
      case 'state':
      case 'tag':
        return filter.type
      case 'date':
        return filter.operation
    }
  }

  private static createTagSuffixShort(filter: Required<Filter>): string {
    const suffix = this.createTagSuffix(filter)

    if (suffix.length) {
      return suffix[0]
    }

    return suffix
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