import { FlagResponse } from '@/types/flagResponse'

export type SettingsResponse = {
  api_url: string,
  csrf_enabled: boolean,
  auth: string | null,
  flags: FlagResponse[],
}