import { Filter } from '@/types/filters/server-types'

export type SavedSearchRequest = {
  name: string,
  filters: Required<Filter>[],
}