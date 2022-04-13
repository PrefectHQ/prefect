import { FilterDateError } from '@/models/FilterDateError'
import { FilterPrefixError } from '@/models/FilterPrefixError'
import {
  Filter,
  FilterObject,
  FilterOperation,
  FilterProperty,
  FilterType,
  FilterValue,
  ObjectStringFilter
} from '@/types/filters'
import { parseDateTimeNumeric } from '@/utilities/dates'

export class FilterParseService {

  private static readonly dateParsers: ((input: string) => Date)[] = [
    parseDateTimeNumeric,
    (input: string) => new Date(input),
  ]

  public static parseFilters(inputs: string[], defaultObject: FilterObject): Required<Filter>[] {
    return inputs.map(input => this.parseFilter(input, defaultObject))
  }

  public static parseFilter(input: string, defaultObject: FilterObject): Required<Filter> {
    const [prefix, ...rest] = input.split(':')
    const value = rest.join(':')

    switch (prefix) {
      case 'd':
      case 'deployment':
        return this.stringFilter('deployment', 'name', value)
      case 'dt':
      case 'deployment_tag':
        return this.tagFilter('deployment', value)
      case 'f':
      case 'flow':
        return this.stringFilter('flow', 'name', value)
      case 'ft':
      case 'flow_tag':
        return this.tagFilter('flow', value)
      case 'fr':
      case 'flow_run':
        return this.stringFilter('flow_run', 'name', value)
      case 'frt':
      case 'flow_run_tag':
        return this.tagFilter('flow_run', value)
      case 'fra':
      case 'flow_run_after':
        return this.dateFilter('flow_run', 'start_date', 'after', value)
      case 'frb':
      case 'flow_run_before':
        return this.dateFilter('flow_run', 'start_date', 'before', value)
      case 'frl':
      case 'flow_run_last':
        return this.filter('flow_run', 'start_date', 'date', 'last', value)
      case 'frn':
      case 'flow_run_next':
        return this.filter('flow_run', 'start_date', 'date', 'next', value)
      case 'frs':
      case 'flow_run_state':
        return this.stateFilter('flow_run', 'state', value)
      case 'tr':
      case 'task_run':
        return this.stringFilter('task_run', 'name', value)
      case 'trt':
      case 'task_run_tag':
        return this.tagFilter('task_run', value)
      case 'tra':
      case 'task_run_after':
        return this.dateFilter('task_run', 'start_date', 'after', value)
      case 'trb':
      case 'task_run_before':
        return this.dateFilter('task_run', 'start_date', 'before', value)
      case 'trl':
      case 'task_run_last':
        return this.filter('task_run', 'start_date', 'date', 'last', value)
      case 'trn':
      case 'task_run_next':
        return this.filter('task_run', 'start_date', 'date', 'next', value)
      case 'trs':
      case 'task_run_state':
        return this.stateFilter('task_run', 'state', value)
      case 'a':
      case 'after':
        return this.dateFilter(defaultObject, 'start_date', 'after', value)
      case 'b':
      case 'before':
        return this.dateFilter(defaultObject, 'start_date', 'before', value)
      case 'n':
      case 'next':
        return this.filter(defaultObject, 'start_date', 'date', 'next', value)
      case 'l':
      case 'last':
        return this.filter(defaultObject, 'start_date', 'date', 'last', value)
      case 's':
      case 'state':
        return this.stateFilter(defaultObject, 'state', value)
      case 't':
      case 'tag':
        return this.tagFilter(defaultObject, value)
      default:
        throw new FilterPrefixError()
    }
  }

  private static stringFilter(object: FilterObject, property: FilterProperty, input: string): Required<Filter> {
    const exactOperationRegex = /^"(.*)"$/
    const match = input.match(exactOperationRegex)

    let value: ObjectStringFilter['value'] = input
    let operation: ObjectStringFilter['operation'] = 'contains'

    if (match) {
      [, value] = match
      operation = 'equals'
    }

    return this.filter(object, property, 'string', operation, value)
  }

  // eslint-disable-next-line max-params
  private static dateFilter(object: FilterObject, property: FilterProperty, operation: FilterOperation, input: string): Required<Filter> {
    const value = this.parseDateValue(input)

    return this.filter(object, property, 'date', operation, value)
  }

  private static tagFilter(object: FilterObject, input: string): Required<Filter> {
    return this.filter(object, 'tag', 'tag', 'and', input.split(','))
  }

  private static stateFilter(object: FilterObject, property: FilterProperty, input: string): Required<Filter> {
    return this.filter(object, property, 'state', 'or', input.toUpperCase().split('|'))
  }

  private static parseDateValue(input: string): Date {
    let value: Date
    const parsers = [...this.dateParsers]

    do {
      const parser = parsers.pop()!
      value = parser(input)
    } while (!this.isValidDate(value) && parsers.length)

    if (!this.isValidDate(value)) {
      throw new FilterDateError()
    }

    return value
  }

  private static isValidDate(input: Date): boolean {
    return !isNaN(input.getTime())
  }


  // eslint-disable-next-line max-params
  private static filter(object: FilterObject, property: FilterProperty, type: FilterType, operation: FilterOperation, value: FilterValue): Required<Filter> {
    return {
      object,
      property,
      type,
      operation,
      value,
    } as Required<Filter>
  }

}