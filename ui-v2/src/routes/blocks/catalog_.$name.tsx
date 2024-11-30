import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'
import { zodSearchValidator } from '@tanstack/router-zod-adapter'
import { useBlockType, buildBlockTypeQuery } from '@/hooks/use-block-types'

const searchParams = z.object({})

function CatalogPage() {
  const { name } = Route.useParams()
  const { blockType } = useBlockType(name)

  return <pre>{JSON.stringify(blockType, null, 2)}</pre>
}

export const Route = createFileRoute('/blocks/catalog_/$name')({
  validateSearch: zodSearchValidator(searchParams),
  component: CatalogPage,
  loader: ({ context, params }) => {
    return context.queryClient.ensureQueryData(buildBlockTypeQuery(params.name))
  },
  wrapInSuspense: true,
})
