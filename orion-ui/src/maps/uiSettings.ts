import { MapFunction } from '@/services/mapper'
import { Settings } from '@/services/uiSettings'
import { SettingsResponse } from '@/types/settingsResponse'
import { FeatureFlag } from '@/utilities/permissions'

export const mapSettingsResponseToSettings: MapFunction<SettingsResponse, Settings> = function(source) {
  return {
    apiUrl: source.api_url,
    flags: this.map('FlagResponse', source.flags, 'Flag').filter(flagIsDefined),
  }
}

function flagIsDefined(flag: FeatureFlag | null): flag is FeatureFlag {
  return flag !== null
}