import { FlagResponse } from '@/types/flag'

export type SettingsResponse = {
  api_url: string,
  flags: FlagResponse[],
}