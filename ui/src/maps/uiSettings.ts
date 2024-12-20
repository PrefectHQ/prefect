import { isNotNullish } from '@prefecthq/prefect-ui-library'
import { MapFunction } from '@/services/mapper'
import { Settings } from '@/services/uiSettings'
import { SettingsResponse } from '@/types/settingsResponse'

export const mapSettingsResponseToSettings: MapFunction<SettingsResponse, Settings> = function(source) {
  return {
    apiUrl: source.api_url,
    csrfEnabled: source.csrf_enabled,
    auth: source.auth,
    flags: this.map('FlagResponse', source.flags, 'FeatureFlag').filter(isNotNullish),
  }
}