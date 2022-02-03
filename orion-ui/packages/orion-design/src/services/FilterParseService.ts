/* eslint-disable default-case */
import {
  Filter,
  FilterObject,
  FilterOperation,
  FilterProperty,
  FilterTagPrefix,
  FilterTagSuffix,
  FilterType,
  FilterValue,
  ObjectDateFilter,
  ObjectFilterTagSuffix,
  ObjectStateFilter,
  ObjectStringFilter,
  ObjectTagFilter,
  ObjectTagPrefixDictionary,
  ObjectTagPrefixes,
  ObjectTagSuffixes,
  ObjectTimeFilter,
  TagPrefixObjectDictionary
} from '../types'
import { parseDateTimeNumeric } from '../utilities/dates'

// export class FilterParseService {

//   private readonly dateParsers: ((input: string) => Date)[] = [parseDateTimeNumeric, (input: string) => new Date(input)]

//   public convertTagsToFilters(tags: string[]): Required<Filter>[] {
//     return tags.map(tag => this.convertTagToFilter(tag))
//   }

//   public convertTagToFilter(tag: string): Required<Filter> {
//     // if(isLongTag) {
//     // return this.parseLongTag(tag)
//     // }

//     return this.parseShortTag(tag)
//   }

//   private parseShortTag(tag: string): Required<Filter> {
//     const object = this.parseObject(tag)
//     const suffix = this.parseSuffix(object, tag)
//     const { type, property } = this.parseTypeAndProperty(object, suffix)
//     const { operation, value } = this.parseOperationAndValue(type, tag, suffix)

//     return {
//       object,
//       property,
//       type,
//       operation,
//       value,
//     } as Required<Filter>
//   }

//   // private parseLongTag(tag: string): any {}

//   private parseObject(tag: string): FilterObject {
//     const prefix = ObjectTagPrefixes.sort((a, b) => b.length - a.length).find(prefix => tag.startsWith(prefix))

//     if (prefix === undefined) {
//       throw 'tag does not start with a valid prefix'
//     }

//     return TagPrefixObjectDictionary[prefix]
//   }

//   private parseSuffix(object: FilterObject, tag: string): FilterTagSuffix {
//     const prefix = ObjectTagPrefixDictionary[object]
//     const regex = new RegExp(`^${prefix}([^:]*):.*$`)
//     const match = tag.match(regex)

//     if (match === null) {
//       throw 'tag does not contain a suffix'
//     }

//     const [, suffix] = match

//     if (!this.isSuffix(suffix)) {
//       throw 'tag does not contain a valid suffix'
//     }

//     return suffix
//   }

//   private parseTypeAndProperty(object: FilterObject, suffix: FilterTagSuffix): { type: FilterType, property: FilterProperty } {
//     switch (object) {
//       case 'flow':
//         return this.parseFlowTypeAndProperty(suffix as ObjectFilterTagSuffix<'flow'>)
//       case 'deployment':
//         return this.parseDeploymentTypeAndProperty(suffix as ObjectFilterTagSuffix<'deployment'>)
//       case 'flow_run':
//       case 'task_run':
//         return this.parseRunTypeAndProperty(suffix as ObjectFilterTagSuffix<'flow_run' | 'task_run'>)
//       case 'tag':
//         return this.parseTagTypeAndProperty(suffix as ObjectFilterTagSuffix<'tag'>)
//     }
//   }

//   private parseFlowTypeAndProperty(suffix: ObjectFilterTagSuffix<'flow'>): { type: FilterType, property: FilterProperty } {
//     switch (suffix) {
//       case '':
//         return { type: 'string', property: 'name' }
//       case 't':
//         return { type: 'tag', property: 'tag' }
//     }
//   }

//   private parseRunTypeAndProperty(suffix: ObjectFilterTagSuffix<'flow_run' | 'task_run'>): { type: FilterType, property: FilterProperty } {
//     switch (suffix) {
//       case '':
//         return { type: 'string', property: 'name' }
//       case 't':
//         return { type: 'tag', property: 'tag' }
//       case 'a':
//       case 'b':
//         return { type: 'date', property: 'start_date' }
//       case 'n':
//       case 'o':
//         return { type: 'time', property: 'start_date' }
//       case 's':
//         return { type: 'state', property: 'state' }
//     }
//   }

//   private parseDeploymentTypeAndProperty(suffix: ObjectFilterTagSuffix<'deployment'>): { type: FilterType, property: FilterProperty } {
//     switch (suffix) {
//       case '':
//         return { type: 'string', property: 'name' }
//       case 't':
//         return { type: 'tag', property: 'tag' }
//     }
//   }

//   private parseTagTypeAndProperty(suffix: ObjectFilterTagSuffix<'tag'>): { type: FilterType, property: FilterProperty } {
//     switch (suffix) {
//       case '':
//         return { type: 'string', property: 'name' }
//     }
//   }

//   private parseOperationAndValue(type: FilterType, tag: string, suffix: FilterTagSuffix): { operation: FilterOperation, value: FilterValue } {
//     const [, ...rest] = tag.split(':')
//     const input = rest.join(':')

//     switch (type) {
//       case 'string':
//         return this.parseStringOperationAndValue(input)
//       case 'tag':
//         return this.parseTagOperationAndValue(input)
//       case 'state':
//         return this.parseStateOperationAndValue(input)
//       case 'date':
//         return this.parseDateOperationAndValue(input, suffix as 'a' | 'b')
//       case 'time':
//         return this.parseTimeOperationAndValue(input, suffix as 'n' | 'o')
//     }
//   }

//   private parseStringOperationAndValue(input: string): { operation: ObjectStringFilter['operation'], value: ObjectStringFilter['value'] } {
//     const exactOperationRegex = /^"(.*)"$/
//     const match = input.match(exactOperationRegex)

//     if (match) {
//       const [, value] = match

//       return {
//         operation: 'equals',
//         value,
//       }
//     }

//     return {
//       operation: 'contains',
//       value: input,
//     }
//   }

//   private parseDateOperationAndValue(input: string, suffix: 'a' | 'b'): { operation: ObjectDateFilter['operation'], value: ObjectDateFilter['value'] } {
//     const value = this.parseDateValue(input)

//     switch (suffix) {
//       case 'a':
//         return { operation: 'after', value }
//       case 'b':
//         return { operation: 'before', value }
//     }
//   }

//   private parseTimeOperationAndValue(input: string, suffix: 'n' | 'o'): { operation: ObjectTimeFilter['operation'], value: ObjectTimeFilter['value'] } {
//     if (!this.isTime(input)) {
//       throw 'invalid time value'
//     }

//     switch (suffix) {
//       case 'n':
//         return { operation: 'newer', value: input }
//       case 'o':
//         return { operation: 'older', value: input }
//     }
//   }

//   private parseTagOperationAndValue(input: string): { operation: ObjectTagFilter['operation'], value: ObjectTagFilter['value'] } {
//     return {
//       operation: 'and',
//       value: input.split(','),
//     }
//   }

//   private parseStateOperationAndValue(input: string): { operation: ObjectStateFilter['operation'], value: ObjectStateFilter['value'] } {
//     return {
//       operation: 'or',
//       value: input.split('|'),
//     }
//   }

//   // using any here because typescript doesn't like string type...
//   // eslint-disable-next-line @typescript-eslint/no-explicit-any
//   private isPrefix(value: any): value is FilterTagPrefix {
//     return ObjectTagPrefixes.includes(value)
//   }

//   // using any here because typescript doesn't like string type...
//   // eslint-disable-next-line @typescript-eslint/no-explicit-any
//   private isSuffix(value: any): value is FilterTagSuffix {
//     return ObjectTagSuffixes.includes(value)
//   }

//   private isTime(value: string): value is ObjectTimeFilter['value'] {
//     return /^[0-1]+[h,d,w,m,w]$/.test(value)
//   }

//   private parseDateValue(input: string): Date {
//     let value: Date
//     const parsers = [...this.dateParsers]

//     do {
//       const parser = parsers.pop()!
//       value = parser(input)
//     } while (!this.isValidDate(value) && parsers.length)

//     if (!this.isValidDate(value)) {
//       throw 'filter date value is invalid'
//     }

//     return value
//   }

//   private isValidDate(input: Date): boolean {
//     return !isNaN(input.getTime())
//   }

// }

export class FilterParseService {

  private readonly dateParsers: ((input: string) => Date)[] = [
    parseDateTimeNumeric,
    (input: string) => new Date(input),
  ]

  public parseFilterString(input: string): Required<Filter> {
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
      case 'fra':
      case 'flow_run_after':
        return this.dateFilter('flow_run', 'start_date', 'after', value)
      case 'frb':
      case 'flow_run_before':
        return this.dateFilter('flow_run', 'start_date', 'before', value)
      case 'frn':
      case 'flow_run_newer':
        return this.filter('flow_run', 'start_date', 'time', 'newer', value)
      case 'frs':
      case 'flow_run_state':
        return this.stateFilter('flow_run', 'state', value)
      case 'tr':
      case 'task_run':
        return this.stringFilter('task_run', 'name', value)
      case 'tra':
      case 'task_run_after':
        return this.dateFilter('task_run', 'start_date', 'after', value)
      case 'trb':
      case 'task_run_before':
        return this.dateFilter('task_run', 'start_date', 'before', value)
      case 'trn':
      case 'task_run_newer':
        return this.filter('task_run', 'start_date', 'time', 'newer', value)
      case 'trs':
      case 'task_run_state':
        return this.stateFilter('task_run', 'state', value)
      default:
        throw 'filter has an invalid prefix'
    }
  }

  private stringFilter(object: FilterObject, property: FilterProperty, input: string): Required<Filter> {
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
  private dateFilter(object: FilterObject, property: FilterProperty, operation: FilterOperation, input: string): Required<Filter> {
    const value = this.parseDateValue(input)

    return this.filter(object, property, 'date', operation, value)
  }

  private tagFilter(object: FilterObject, input: string): Required<Filter> {
    return this.filter(object, 'tag', 'tag', 'and', input.split(','))
  }

  private stateFilter(object: FilterObject, property: FilterProperty, input: string): Required<Filter> {
    return this.filter(object, property, 'state', 'or', input.split('|'))
  }

  private parseDateValue(input: string): Date {
    let value: Date
    const parsers = [...this.dateParsers]

    do {
      const parser = parsers.pop()!
      value = parser(input)
    } while (!this.isValidDate(value) && parsers.length)

    if (!this.isValidDate(value)) {
      throw 'filter date value is invalid'
    }

    return value
  }

  private isValidDate(input: Date): boolean {
    return !isNaN(input.getTime())
  }


  // eslint-disable-next-line max-params
  private filter(object: FilterObject, property: FilterProperty, type: FilterType, operation: FilterOperation, value: FilterValue): Required<Filter> {
    return {
      object,
      property,
      type,
      operation,
      value,
    } as Required<Filter>
  }

}