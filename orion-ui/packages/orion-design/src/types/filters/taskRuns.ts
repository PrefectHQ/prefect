import { ObjectStringFilter, ObjectDateFilter, ObjectTagFilter, ObjectStateFilter, ObjectRelativeDateFilter } from '.'

export type TaskRunFilter = {
  object: 'task_run',
} & Partial<(TaskRunStringFilter | TaskRunDateFilter | TaskRunRelativeDateFilter | TaskRunTagFilter | TaskRunStateFilter)>

export type TaskRunStringFilter = {
  object: 'task_run',
  property: 'name',
} & Partial<ObjectStringFilter>

export type TaskRunDateFilter = {
  object: 'task_run',
  property: 'start_date',
} & Partial<ObjectDateFilter>

export type TaskRunRelativeDateFilter = {
  object: 'task_run',
  property: 'start_date',
} & Partial<ObjectRelativeDateFilter>

export type TaskRunTagFilter = {
  object: 'task_run',
  property: 'tag',
} & Partial<ObjectTagFilter>

export type TaskRunStateFilter = {
  object: 'task_run',
  property: 'state',
} & Partial<ObjectStateFilter>