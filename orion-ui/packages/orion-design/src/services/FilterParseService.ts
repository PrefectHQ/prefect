/* eslint-disable default-case */
import {
  Filter,
  FilterObject,
  FilterOperation,
  FilterProperty,
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

export class FilterParseService {
  public convertTagsToFilters(tags: string[]): Required<Filter>[] {
    return tags.map(tag => this.convertTagToFilter(tag))
  }

  public convertTagToFilter(tag: string): Required<Filter> {
    // if(isLongTag) {
    // return this.parseLongTag(tag)
    // }

    return this.parseShortTag(tag)
  }

  private parseShortTag(tag: string): Required<Filter> {
    const object = this.parseObject(tag)
    const suffix = this.parseSuffix(object, tag)
    const { type, property } = this.parseTypeAndProperty(object, suffix)
    const { operation, value } = this.parseOperationAndValue(type, tag, suffix)

    return {
      object,
      property,
      type,
      operation,
      value,
    } as Required<Filter>
  }

  // private parseLongTag(tag: string): any {}

  private parseObject(tag: string): FilterObject {
    const prefix = ObjectTagPrefixes.find(prefix => tag.startsWith(prefix))

    if (prefix === undefined) {
      throw 'tag does not start with a valid prefix'
    }

    return TagPrefixObjectDictionary[prefix]
  }

  private parseSuffix(object: FilterObject, tag: string): FilterTagSuffix {
    const prefix = ObjectTagPrefixDictionary[object]
    const regex = new RegExp(`${prefix}(.*):.*`)
    const match = tag.match(regex)

    if (match === null) {
      throw 'tag does not contain a suffix'
    }

    const [, suffix] = match

    if (!this.isSuffix(suffix)) {
      throw 'tag does not contain a valid suffix'
    }

    return suffix
  }

  private parseTypeAndProperty(object: FilterObject, suffix: FilterTagSuffix): { type: FilterType, property: FilterProperty } {
    switch (object) {
      case 'flow':
        return this.parseFlowTypeAndProperty(suffix as ObjectFilterTagSuffix<'flow'>)
      case 'deployment':
        return this.parseDeploymentTypeAndProperty(suffix as ObjectFilterTagSuffix<'deployment'>)
      case 'flow_run':
      case 'task_run':
        return this.parseRunTypeAndProperty(suffix as ObjectFilterTagSuffix<'flow_run' | 'task_run'>)
      case 'tag':
        return this.parseTagTypeAndProperty(suffix as ObjectFilterTagSuffix<'tag'>)
    }
  }

  private parseFlowTypeAndProperty(suffix: ObjectFilterTagSuffix<'flow'>): { type: FilterType, property: FilterProperty } {
    switch (suffix) {
      case '':
        return { type: 'string', property: 'name' }
      case 't':
        return { type: 'tag', property: 'tag' }
    }
  }

  private parseRunTypeAndProperty(suffix: ObjectFilterTagSuffix<'flow_run' | 'task_run'>): { type: FilterType, property: FilterProperty } {
    switch (suffix) {
      case '':
        return { type: 'string', property: 'name' }
      case 't':
        return { type: 'tag', property: 'tag' }
      case 'a':
      case 'b':
        return { type: 'date', property: 'start_date' }
      case 'n':
      case 'o':
        return { type: 'time', property: 'start_date' }
    }
  }

  private parseDeploymentTypeAndProperty(suffix: ObjectFilterTagSuffix<'deployment'>): { type: FilterType, property: FilterProperty } {
    switch (suffix) {
      case '':
        return { type: 'string', property: 'name' }
      case 't':
        return { type: 'tag', property: 'tag' }
    }
  }

  private parseTagTypeAndProperty(suffix: ObjectFilterTagSuffix<'tag'>): { type: FilterType, property: FilterProperty } {
    switch (suffix) {
      case '':
        return { type: 'string', property: 'name' }
    }
  }

  private parseOperationAndValue(type: FilterType, tag: string, suffix: FilterTagSuffix): { operation: FilterOperation, value: FilterValue } {
    const [, input] = tag.split(':')

    switch (type) {
      case 'string':
        return this.parseStringOperationAndValue(input)
      case 'tag':
        return this.parseTagOperationAndValue(input)
      case 'state':
        return this.parseStateOperationAndValue(input)
      case 'date':
        return this.parseDateOperationAndValue(input, suffix as 'a' | 'b')
      case 'time':
        return this.parseTimeOperationAndValue(input, suffix as 'n' | 'o')
    }
  }

  private parseStringOperationAndValue(input: string): { operation: ObjectStringFilter['operation'], value: ObjectStringFilter['value'] } {
    const exactOperationRegex = /^"(.*)"$/
    const match = input.match(exactOperationRegex)

    if (match) {
      const [, value] = match

      return {
        operation: 'equals',
        value,
      }
    }

    return {
      operation: 'contains',
      value: input,
    }
  }

  private parseDateOperationAndValue(input: string, suffix: 'a' | 'b'): { operation: ObjectDateFilter['operation'], value: ObjectDateFilter['value'] } {
    const value = new Date(input)

    switch (suffix) {
      case 'a':
        return { operation: 'after', value }
      case 'b':
        return { operation: 'before', value }
    }
  }

  private parseTimeOperationAndValue(input: string, suffix: 'n' | 'o'): { operation: ObjectTimeFilter['operation'], value: ObjectTimeFilter['value'] } {
    if (!this.isTime(input)) {
      throw 'invalid time value'
    }

    switch (suffix) {
      case 'n':
        return { operation: 'newer', value: input }
      case 'o':
        return { operation: 'older', value: input }
    }
  }

  private parseTagOperationAndValue(input: string): { operation: ObjectTagFilter['operation'], value: ObjectTagFilter['value'] } {
    return {
      operation: 'and',
      value: input.split(','),
    }
  }

  private parseStateOperationAndValue(input: string): { operation: ObjectStateFilter['operation'], value: ObjectStateFilter['value'] } {
    return {
      operation: 'or',
      value: input.split(','),
    }
  }

  // using any here because typescript doesn't like string type...
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private isSuffix(value: any): value is FilterTagSuffix {
    return ObjectTagSuffixes.includes(value)
  }

  private isTime(value: string): value is ObjectTimeFilter['value'] {
    return /^[0-1]+[h,d,w,m,w]$/.test(value)
  }

}