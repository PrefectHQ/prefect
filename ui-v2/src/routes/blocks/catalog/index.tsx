import { createFileRoute } from '@tanstack/react-router'
import { Link } from '@tanstack/react-router'
import { useListBlockTypes } from '@/hooks/block-types'
import { Button } from '@/components/ui/button'
import type { components } from '@/api/prefect'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

type BlockType = components['schemas']['BlockType']

function BlockTypeCard({ blockType }: { blockType: BlockType }) {
  return (
    <div className="p-4 border rounded h-[180px] flex flex-col">
      <div className="flex-1">
        <div className="flex items-center gap-3">
          <Avatar className="h-8 w-8">
            <AvatarImage src={blockType.logo_url ?? ''} alt={blockType.name} />
            <AvatarFallback>{blockType.name.charAt(0)}</AvatarFallback>
          </Avatar>
          <h3 className="font-medium">{blockType.name}</h3>
        </div>
        {blockType.description && (
          <p className="text-sm text-gray-600 mt-1 line-clamp-3">{blockType.description}</p>
        )}
      </div>
      <div className="mt-4 flex gap-2">
        <Button asChild className="flex-1">
          <Link
            to="/blocks/catalog/$blockTypeSlug/create"
            params={{ blockTypeSlug: blockType.slug }}
          >
            Create
          </Link>
        </Button>
        <Button variant="outline" asChild className="flex-1">
          <Link
            to="/blocks/catalog/$blockTypeSlug"
            params={{ blockTypeSlug: blockType.slug }}
          >
            Details
          </Link>
        </Button>
      </div>
    </div>
  )
}

export const Route = createFileRoute('/blocks/catalog/')({
  component: () => {
    const { data: blockTypes } = useListBlockTypes()

    return (
      <div className="p-4">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-bold">Block Catalog</h1>

        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {blockTypes.map((blockType) => (
            <BlockTypeCard key={blockType.id} blockType={blockType} />
          ))}
        </div>
      </div>
    )
  },
  loader: useListBlockTypes.loader
})
