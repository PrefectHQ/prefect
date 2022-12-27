import { maps as designMaps } from '@prefecthq/orion-design'
import { mapFlagResponseToFeatureFlag } from '@/maps/featureFlag'
import { mapSettingsResponseToSettings } from '@/maps/uiSettings'

export const maps = {
  ...designMaps,
  FlagResponse: { Flag: mapFlagResponseToFeatureFlag },
  SettingsResponse: { Settings: mapSettingsResponseToSettings },
}