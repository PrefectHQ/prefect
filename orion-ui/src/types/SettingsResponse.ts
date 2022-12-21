import { FlagResponse } from '@/types/FlagResponse'

export type SettingsResponse = {
  api_url: string,
  flags: FlagResponse[],
}