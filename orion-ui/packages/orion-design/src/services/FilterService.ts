/* eslint-disable no-dupe-class-members */
import { Filter } from '../types/filters'
import { FilterParseService, FilterStringifyService } from '.'

export class FilterService {
  public static stringify(filter: Required<Filter>): string
  public static stringify(filters: Required<Filter>[]): string[]
  public static stringify(filterOrFilters: Required<Filter> | Required<Filter>[]): string | string[] {
    if (Array.isArray(filterOrFilters)) {
      return FilterStringifyService.convertFiltersToTags(filterOrFilters)
    }

    return FilterStringifyService.convertFilterToTag(filterOrFilters)
  }

  public static parse(filter: string): Required<Filter>
  public static parse(filters: string[]): Required<Filter>[]
  public static parse(filterOrFilters: string | string[]): Required<Filter> | Required<Filter>[] {
    if (Array.isArray(filterOrFilters)) {
      return FilterParseService.parseFilterStrings(filterOrFilters)
    }

    return FilterParseService.parseFilterString(filterOrFilters)
  }
}