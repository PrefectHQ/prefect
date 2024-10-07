import { createFileRoute } from '@tanstack/react-router'
import { QueryService } from '@/api/service'
import FlowsTable from '@/components/flows/data-table'
import { z } from 'zod'
import { zodSearchValidator } from '@tanstack/router-zod-adapter'
import { useSuspenseQuery } from '@tanstack/react-query'

const searchParams = z
  .object({
    page: z.number().int().positive().optional().default(1),
    limit: z.number().int().positive().max(100).optional().default(10),
    sort: z
      .enum(["CREATED_DESC", "UPDATED_DESC",  "NAME_ASC", "NAME_DESC"])
      .optional()
      .default('CREATED_DESC'),
  })
  .optional()
  .default({})

const flowsQueryParams = (search: z.infer<typeof searchParams>) => ({
  queryKey: ['flows', JSON.stringify(search)],
  queryFn: async () =>
    await QueryService.POST('/flows/paginate', {
      body: {
        page: search.page,
        limit: search.limit,
        sort: search.sort,
      },
    }),
  staleTime: 1000, // Data will be considered stale after 1 second.
})

export const Route = createFileRoute('/flows/')({
  component: () => {
    const search = Route.useSearch()
    const { data } = useSuspenseQuery(flowsQueryParams(search))
    
    
    return <FlowsTable flows={data.data?.results} />
  },
  loaderDeps: ({ search }) => search,
  loader: async ({ deps: search, context }) =>
    await context.queryClient.ensureQueryData(flowsQueryParams(search)),
  validateSearch: zodSearchValidator(searchParams),
  wrapInSuspense: true,
})
