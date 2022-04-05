import { DeploymentFilter } from './deployments'
import { FlowRunFilter } from './flowRuns'
import { FlowFilter } from './flows'
import { TagFilter } from './tags'
import { TaskRunFilter } from './taskRuns'
import { StateType } from '@/models/StateType'
import { flip } from '@/utilities/object'

export type RelativeDateFilterValue = `${number}h` | `${number}d` | `${number}w` | `${number}m` | `${number}y`

export type ObjectStringFilter = {
  type: 'string',
  operation: 'contains' | 'equals',
  value: string,
}

export type ObjectDateFilter = {
  type: 'date',
  operation: 'after' | 'before',
  value: Date,
}

export type ObjectRelativeDateFilter = {
  type: 'date',
  operation: 'next' | 'last',
  value: RelativeDateFilterValue,
}

export type ObjectTagFilter = {
  type: 'tag',
  operation: 'and',
  value: string[],
}

export type ObjectStateFilter = {
  type: 'state',
  operation: 'or',
  value: StateType[],
}

export type ObjectNumberFilter = {
  type: 'number',
  operation: 'less' | 'more',
  value: number,
}

export type Filter = FlowFilter | DeploymentFilter | FlowRunFilter | TaskRunFilter | TagFilter
export type FilterObject = Filter['object']
export type FilterProperty = Required<Filter>['property']
export type FilterOperation = Required<Filter>['operation']
export type FilterType = Required<Filter>['type']
export type FilterValue = Required<Filter>['value']
export type ObjectFilter = Pick<Required<Filter>, 'type' | 'operation' | 'value'>

const ObjectTagPrefixDictionaryData = {
  'deployment': 'd',
  'flow': 'f',
  'flow_run': 'fr',
  'task_run': 'tr',
  'tag': 't',
} as const

const ObjectTagSuffixDictionaryData = {
  'deployment': ['', 't'],
  'flow': ['', 't'],
  'flow_run': ['', 't', 's', 'a', 'b', 'n', 'o'],
  'task_run': ['', 't', 's', 'a', 'b', 'n', 'o'],
  'tag': [''],
} as const

export type FilterTagPrefix = typeof ObjectTagPrefixDictionaryData[FilterObject]
export type FilterTagSuffix = typeof ObjectTagSuffixDictionaryData[FilterObject][number]

export type ObjectFilterTagSuffix<T extends FilterObject> = typeof ObjectTagSuffixDictionaryData[T][number]

export type FilterOfObject<T extends FilterObject> = Extract<Filter, { object: T }>

export const ObjectTagPrefixes = Object.values(ObjectTagPrefixDictionaryData)
export const ObjectTagSuffixes = Object.values(ObjectTagSuffixDictionaryData).flat()
export const TagPrefixObjectDictionary = flip(ObjectTagPrefixDictionaryData)
export const ObjectTagPrefixDictionary = flip(TagPrefixObjectDictionary)

export * from './deployments'
export * from './flowRuns'
export * from './flows'
export * from './tags'
export * from './taskRuns'