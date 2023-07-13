import { WorkspaceFeatureFlag } from '@prefecthq/prefect-ui-library'
import { MapFunction } from '@/services/mapper'
import { FlagResponse } from '@/types/flagResponse'
import { FeatureFlag } from '@/utilities/permissions'

export const mapFlagResponseToFeatureFlag: MapFunction<FlagResponse, FeatureFlag | WorkspaceFeatureFlag | null> = (source) => {
  switch (source) {
    case 'workers':
      return 'access:workers'
    case 'work_pools':
      return 'access:work_pools'
    case 'artifacts':
      return 'access:artifacts'
    default:
      return null
  }
}