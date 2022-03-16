import { ObjectStringFilter, ObjectTagFilter } from '.'

export type DeploymentFilter = {
  object: 'deployment',
} & Partial<(DeploymentStringFilter | DeploymentTagFilter)>

export type DeploymentStringFilter = {
  object: 'deployment',
  property: 'name',
} & Partial<ObjectStringFilter>

export type DeploymentTagFilter = {
  object: 'deployment',
  property: 'tag',
} & Partial<ObjectTagFilter>