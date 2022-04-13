import { Filter } from '@/types/filters'

export type SavedSearchRequest = {
  name: string,
  filters: Required<Filter>[],
}