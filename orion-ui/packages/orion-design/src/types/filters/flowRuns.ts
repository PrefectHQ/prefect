import { EntityStringFilter, EntityDateFilter, EntityTagFilter, EntityStateFilter } from '.'

export type FlowRunFilter = {
  entity: 'flow_run',
} & Partial<(FlowRunStringFilter | FlowRunDateFilter | FlowRunTagFilter | FlowRunStateFilter)>

export type FlowRunStringFilter = {
  entity: 'flow_run',
  key: 'name',
} & Partial<EntityStringFilter>

export type FlowRunDateFilter = {
  entity: 'flow_run',
  key: 'start_date' | 'end_date',
} & Partial<EntityDateFilter>

export type FlowRunTagFilter = {
  entity: 'flow_run',
  key: 'tag',
} & Partial<EntityTagFilter>

export type FlowRunStateFilter = {
  entity: 'flow_run',
  key: 'state',
} & Partial<EntityStateFilter>