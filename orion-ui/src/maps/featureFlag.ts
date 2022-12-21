import { MapFunction } from '@/services/mapper'
import { FlagResponse } from '@/types/FlagResponse'
import { FeatureFlag } from '@/utilities/permissions'

export const mapFlagResponseToFeatureFlag: MapFunction<FlagResponse, FeatureFlag> = (source) => {
  switch (source) {
    case 'magic':
      return 'access:magic'
    case 'wizardry':
      return 'access:wizardry'
    case 'alchemy':
      return 'access:alchemy'
    case 'witchcraft':
      return 'access:witchcraft'
    default:
      throw new Error(`Invalid FlagResponse in mapper ${source}`)
  }
}