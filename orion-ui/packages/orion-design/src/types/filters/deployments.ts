import { ObjectStringFilter, ObjectTagFilter } from '.'

export type DeploymentFilter = {
  object: 'deployment',
} & Partial<(DeploymentStringFilter | DeploymentTagFilter)>

export type DeploymentStringFilter = {
  object: 'deployment',
  key: 'name',
} & Partial<ObjectStringFilter>

export type DeploymentTagFilter = {
  object: 'deployment',
  key: 'tag',
} & Partial<ObjectTagFilter>