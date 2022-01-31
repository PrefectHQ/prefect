import { ObjectStringFilter, ObjectTagFilter } from '.'

export type FlowFilter = {
  object: 'flow',
} & Partial<(FlowStringFilter | FlowTagFilter)>

export type FlowStringFilter = {
  object: 'flow',
  property: 'name',
} & Partial<ObjectStringFilter>

export type FlowTagFilter = {
  object: 'flow',
  property: 'tag',
} & Partial<ObjectTagFilter>