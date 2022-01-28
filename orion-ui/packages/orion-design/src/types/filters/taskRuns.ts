import { ObjectStringFilter, ObjectDateFilter, ObjectTagFilter, ObjectStateFilter } from '.'

export type TaskRunFilter = {
  object: 'task_run',
} & Partial<(TaskRunStringFilter | TaskRunDateFilter | TaskRunTagFilter | TaskRunStateFilter)>

export type TaskRunStringFilter = {
  object: 'task_run',
  key: 'name',
} & Partial<ObjectStringFilter>

export type TaskRunDateFilter = {
  object: 'task_run',
  key: 'start_date' | 'end_date',
} & Partial<ObjectDateFilter>

export type TaskRunTagFilter = {
  object: 'task_run',
  key: 'tag',
} & Partial<ObjectTagFilter>

export type TaskRunStateFilter = {
  object: 'task_run',
  key: 'state',
} & Partial<ObjectStateFilter>