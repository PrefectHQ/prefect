import { ObjectStringFilter } from '.'

export type TagFilter = {
  object: 'tag',
} & Partial<TagStringFilter>

export type TagStringFilter = {
  object: 'tag',
  property: 'name',
} & Partial<ObjectStringFilter>