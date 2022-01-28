import { EntityStringFilter, EntityTagFilter } from '.'

export type DeploymentFilter = {
  entity: 'deployment',
} & Partial<(DeploymentStringFilter | DeploymentTagFilter)>

export type DeploymentStringFilter = {
  entity: 'deployment',
  key: 'name',
} & Partial<EntityStringFilter>

export type DeploymentTagFilter = {
  entity: 'deployment',
  key: 'tag',
} & Partial<EntityTagFilter>