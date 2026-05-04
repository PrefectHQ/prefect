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
    defaultUi: source.default_ui ?? 'v1',
    availableUis: source.available_uis ?? [],
    v1BaseUrl: source.v1_base_url ?? null,
    v2BaseUrl: source.v2_base_url ?? null,
  }
}
