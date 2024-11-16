import { getQueryService } from '@/api/service'
import { keepPreviousData, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'

const buildWorkPoolTypesQuery = () => ({
  queryKey: ['work-pool-types'],
  queryFn: async () => {
    const response = await getQueryService().GET('/collections/views/{view}', {
      params: {
        path: {
          view: 'aggregate-worker-metadata'
        }
      }
    })
    return response.data
  },
  staleTime: 1000,
  placeholderData: keepPreviousData,
})

function RouteComponent() {
  const { data: workPoolTypes } = useSuspenseQuery(buildWorkPoolTypesQuery())
  return JSON.stringify(workPoolTypes)
}

export const Route = createFileRoute('/work-pools/create')({
  component: RouteComponent,
  loader: ({ context }) => 
    context.queryClient.ensureQueryData(buildWorkPoolTypesQuery()),
  wrapInSuspense: true,
})
