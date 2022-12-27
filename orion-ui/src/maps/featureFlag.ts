import { MapFunction } from '@/services/mapper'
import { FlagResponse } from '@/types/flagResponse'
import { FeatureFlag } from '@/utilities/permissions'

export const mapFlagResponseToFeatureFlag: MapFunction<FlagResponse, FeatureFlag | null> = (source) => {
  switch (source) {
    // case 'magic':
    //   return 'access:magic'
    default:
      return null
  }
}