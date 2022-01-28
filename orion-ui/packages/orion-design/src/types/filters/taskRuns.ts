import { EntityStringFilter, EntityDateFilter, EntityTagFilter, EntityStateFilter } from '.'

export type TaskRunFilter = {
  entity: 'task_run',
} & Partial<(TaskRunStringFilter | TaskRunDateFilter | TaskRunTagFilter | TaskRunStateFilter)>

export type TaskRunStringFilter = {
  entity: 'task_run',
  key: 'name',
} & Partial<EntityStringFilter>

export type TaskRunDateFilter = {
  entity: 'task_run',
  key: 'start_date' | 'end_date',
} & Partial<EntityDateFilter>

export type TaskRunTagFilter = {
  entity: 'task_run',
  key: 'tag',
} & Partial<EntityTagFilter>

export type TaskRunStateFilter = {
  entity: 'task_run',
  key: 'state',
} & Partial<EntityStateFilter>