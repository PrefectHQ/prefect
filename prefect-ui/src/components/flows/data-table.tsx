
import { components } from '@/api/prefect'
import { columns } from './columns'
import { DataTable } from '@/components/ui/data-table'
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDownIcon, SearchIcon } from 'lucide-react'

const SearchComponent = () => (
  <div className="relative">
    <Input placeholder="Flow names" className="pl-10" />
    <SearchIcon className="absolute left-3 top-2.5 text-muted-foreground" size={18} />
  </div>
)

const FilterComponent = () => (
  <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <Button variant="outline">
        All tags <ChevronDownIcon className="ml-2 h-4 w-4" />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent>
      <DropdownMenuItem>Tag 1</DropdownMenuItem>
      <DropdownMenuItem>Tag 2</DropdownMenuItem>
      <DropdownMenuItem>Tag 3</DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
)

const SortComponent = () => (
  <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <Button variant="outline">
        A to Z <ChevronDownIcon className="ml-2 h-4 w-4" />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent>
      <DropdownMenuItem>A to Z</DropdownMenuItem>
      <DropdownMenuItem>Z to A</DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
)

export default function FlowsTable({
  flows
}: {
  flows: components['schemas']['Flow'][] 
}) {
  return (
    <div className="h-full">
      <header className="mb-6 flex flex-row justify-between">
        <h1 className="flex self-center">{flows.length} Flows</h1>
        <div className="flex space-x-4">
          <SearchComponent />
          <FilterComponent />
          <SortComponent />
        </div>
      </header>
      <div className="rounded-md border">
        <DataTable columns={columns} data={flows} />
      </div>
    </div>
  )
}