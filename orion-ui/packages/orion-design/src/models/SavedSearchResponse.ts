import { Filter } from '@/types/filters'

export type SavedSearchResponse = {
  id: string,
  created: string,
  updated: string,
  name: string,
  filters: Required<Filter>[],
}