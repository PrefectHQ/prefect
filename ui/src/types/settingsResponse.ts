import { FlagResponse } from '@/types/flagResponse'

export type SettingsResponse = {
  api_url: string,
  csrf_enabled: boolean,
  auth: string | null,
  flags: FlagResponse[],
  default_ui?: 'v1' | 'v2',
  available_uis?: Array<'v1' | 'v2'>,
  v1_base_url?: string | null,
  v2_base_url?: string | null,
}
