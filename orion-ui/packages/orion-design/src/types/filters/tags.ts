import { EntityStringFilter } from '.'

export type TagFilter = {
  entity: 'tag',
} & Partial<TagStringFilter>

export type TagStringFilter = {
  entity: 'tag',
  key: 'name',
} & Partial<EntityStringFilter>