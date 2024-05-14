import { maps as designMaps } from '@prefecthq/prefect-ui-library'
import { mapAutomationCreateToAutomationCreateRequest, mapAutomationResponseToAutomation } from '@/maps/automation'
import { mapCsrfTokenResponseToCsrfToken } from '@/maps/csrfToken'
import { mapFlagResponseToFeatureFlag } from '@/maps/featureFlag'
import { mapSettingsResponseToSettings } from '@/maps/uiSettings'

export const maps = {
  ...designMaps,
  FlagResponse: { FeatureFlag: mapFlagResponseToFeatureFlag },
  SettingsResponse: { Settings: mapSettingsResponseToSettings },
  CsrfTokenResponse: { CsrfToken: mapCsrfTokenResponseToCsrfToken },
  AutomationResponse: { Automation: mapAutomationResponseToAutomation },
  AutomationCreate: { AutomationCreateRequest: mapAutomationCreateToAutomationCreateRequest },
}
