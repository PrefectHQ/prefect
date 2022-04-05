import { InjectionKey } from 'vue'
import { UnionFilters } from '@/services/Filter'
import { FilterDescriptionService } from '@/services/FilterDescriptionService'
import { FilterParseService } from '@/services/FilterParseService'
import { FiltersQueryService } from '@/services/FiltersQueryService'
import { FilterStringifyOptions, FilterStringifyService } from '@/services/FilterStringifyService'
import { Filter, FilterObject } from '@/types/filters'

export class FilterService {
  public static stringify(filter: Required<Filter>, options?: FilterStringifyOptions): string
  public static stringify(filters: Required<Filter>[], options?: FilterStringifyOptions): string[]
  public static stringify(filterOrFilters: Required<Filter> | Required<Filter>[], options?: FilterStringifyOptions): string | string[] {
    if (Array.isArray(filterOrFilters)) {
      return FilterStringifyService.stringifyFilters(filterOrFilters, options)
    }

    return FilterStringifyService.stringifyFilter(filterOrFilters, options)
  }

  public static parse(filter: string, defaultObject: FilterObject): Required<Filter>
  public static parse(filters: string[], defaultObject: FilterObject): Required<Filter>[]
  public static parse(filterOrFilters: string | string[], defaultObject: FilterObject): Required<Filter> | Required<Filter>[] {
    if (Array.isArray(filterOrFilters)) {
      return FilterParseService.parseFilters(filterOrFilters, defaultObject)
    }

    return FilterParseService.parseFilter(filterOrFilters, defaultObject)
  }

  public static query(filters: Required<Filter>[]): UnionFilters {
    return FiltersQueryService.query(filters)
  }

  public static describe(filter: Filter): string {
    return FilterDescriptionService.describe(filter)
  }

  public static icon(filter: Filter): string {
    // eslint-disable-next-line default-case
    switch (filter.object) {
      case 'flow':
        return 'pi-flow'
      case 'deployment':
        return 'pi-map-pin-line'
      case 'flow_run':
        return 'pi-flow-run'
      case 'task_run':
        return 'pi-task'
      case 'tag':
        return 'pi-label'
    }
  }
}

export const filtersDefaultObjectKey: InjectionKey<FilterObject> = Symbol('filtersDefaultObjectKey')