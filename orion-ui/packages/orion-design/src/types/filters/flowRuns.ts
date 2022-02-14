import { ObjectStringFilter, ObjectDateFilter, ObjectTagFilter, ObjectStateFilter, ObjectRelativeDateFilter } from '.'

export type FlowRunFilter = {
  object: 'flow_run',
} & Partial<(FlowRunStringFilter | FlowRunDateFilter | FlowRunRelativeDateFilter | FlowRunTagFilter | FlowRunStateFilter)>

export type FlowRunStringFilter = {
  object: 'flow_run',
  property: 'name',
} & Partial<ObjectStringFilter>

export type FlowRunDateFilter = {
  object: 'flow_run',
  property: 'start_date',
} & Partial<ObjectDateFilter>

export type FlowRunRelativeDateFilter = {
  object: 'flow_run',
  property: 'start_date',
} & Partial<ObjectRelativeDateFilter>

export type FlowRunTagFilter = {
  object: 'flow_run',
  property: 'tag',
} & Partial<ObjectTagFilter>

export type FlowRunStateFilter = {
  object: 'flow_run',
  property: 'state',
} & Partial<ObjectStateFilter>