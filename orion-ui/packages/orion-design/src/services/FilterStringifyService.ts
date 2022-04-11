import {
  Filter,
  ObjectDateFilter,
  ObjectStateFilter,
  ObjectStringFilter,
  ObjectTagFilter,
  ObjectRelativeDateFilter,
  ObjectTagPrefixDictionary,
  FilterObject
} from '@/types/filters'
import { formatDateTimeNumericInTimeZone } from '@/utilities/dates'

export type FilterStringifyMethod = 'short' | 'full'
export type FilterStringifyOptions = {
  method?: FilterStringifyMethod,
  defaultObject?: FilterObject,
}

export class FilterStringifyService {
  public static stringifyFilters(filters: Required<Filter>[], options?: FilterStringifyOptions): string[] {
    return filters.map(filter => this.stringifyFilter(filter, options))
  }

  public static stringifyFilter(filter: Required<Filter>, options?: FilterStringifyOptions): string {
    const short = options?.method === 'short'
    const tag = short ? this.createTagShort(filter, options.defaultObject) : this.createTag(filter, options?.defaultObject)
    const value = this.createTagValue(filter)

    if(tag == '') {
      return value
    }

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

  private static createObjectDateFilterValue(filter: ObjectDateFilter | ObjectRelativeDateFilter): string {
    switch (filter.operation) {
      case 'after':
      case 'before':
        return formatDateTimeNumericInTimeZone(filter.value)
      case 'next':
      case 'last':
        return filter.value
    }
  }

  private static createObjectStateFilterValue(filter: ObjectStateFilter): string {
    return filter.value.join('|')
  }

  private static createObjectTagFilterValue(filter: ObjectTagFilter): string {
    return filter.value.join(',')
  }

  private static createTag(filter: Required<Filter>, defaultObject?: FilterObject): string {
    const prefix = this.createTagPrefix(filter)
    const suffix = this.createTagSuffix(filter)

    if (defaultObject) {
      const filterWithDefaultObject = { ...filter, object: defaultObject } as Required<Filter>

      try {
        const prefixForFilterWithDefaultObject = this.createTagPrefix(filterWithDefaultObject)

        if (prefixForFilterWithDefaultObject === prefix) {
          return suffix
        }
      } catch { /* silence is golden */ }
    }

    if (suffix.length) {
      return `${prefix}_${suffix}`
    }

    return prefix
  }

  private static createTagShort(filter: Required<Filter>, defaultObject?: FilterObject): string {
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