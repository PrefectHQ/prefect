import { reactive } from 'vue'
import { useRouteParam } from '@/compositions/useRouteParam'
import { OrionContext } from '@/types/OrionContext'


export function useRouteContext(): OrionContext {

  return reactive({
    accountId: useRouteParam('accountId'),
    workspaceId: useRouteParam('workspaceId'),
  })
}