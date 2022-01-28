import { ObjectStringFilter, ObjectTagFilter } from '.'

export type FlowFilter = {
  object: 'flow',
} & Partial<(FlowStringFilter | FlowTagFilter)>

export type FlowStringFilter = {
  object: 'flow',
  key: 'name',
} & Partial<ObjectStringFilter>

export type FlowTagFilter = {
  object: 'flow',
  key: 'tag',
} & Partial<ObjectTagFilter>