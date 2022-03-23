import { Filter } from '@/types/filters/server-types'

export type SavedSearchResponse = {
  id: string,
  created: string,
  updated: string,
  name: string,
  filters: Required<Filter>[],
}