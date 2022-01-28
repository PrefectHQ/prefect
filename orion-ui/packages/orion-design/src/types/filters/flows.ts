import { EntityStringFilter, EntityTagFilter } from '.'

export type FlowFilter = {
  entity: 'flow',
} & Partial<(FlowStringFilter | FlowTagFilter)>

export type FlowStringFilter = {
  entity: 'flow',
  key: 'name' | 'title',
} & Partial<EntityStringFilter>

export type FlowTagFilter = {
  entity: 'flow',
  key: 'tag',
} & Partial<EntityTagFilter>