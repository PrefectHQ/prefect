import { WorkspaceFeatureFlag } from '@prefecthq/prefect-ui-library'
import { MapFunction } from '@/services/mapper'
import { FlagResponse } from '@/types/flagResponse'
import { FeatureFlag } from '@/utilities/permissions'

export const mapFlagResponseToFeatureFlag: MapFunction<FlagResponse, FeatureFlag | WorkspaceFeatureFlag | null> = (source) => {
  switch (source) {
    case 'workers':
      return 'access:workers'
    case 'artifacts':
      return 'access:artifacts'
    default:
      // we want to have a ts error here but we don't want to break the app so returning null rather than throwing an error
      // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
      const exhaustiveCheck: never = source
      return null
  }
}
