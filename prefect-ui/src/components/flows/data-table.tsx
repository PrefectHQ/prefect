
import { components } from '@/api/prefect'
import { columns } from './columns'
import { DataTable } from '@/components/ui/data-table'
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { useNavigate } from "@tanstack/react-router"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDownIcon, SearchIcon } from 'lucide-react'
import { useState } from 'react'
import { getCoreRowModel, getPaginationRowModel, useReactTable } from '@tanstack/react-table'

const SearchComponent = () => {
  const navigate = useNavigate()

  return <div className="relative">
    <Input placeholder="Flow names" className="pl-10" onChange={(e) => navigate({ to: '.', search: (prev) => ({ ...prev, name: e.target.value }) })} />
    <SearchIcon className="absolute left-3 top-2.5 text-muted-foreground" size={18} />
  </div>
}
const FilterComponent = () => {
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [open, setOpen] = useState(false);

  const toggleTag = (tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const renderSelectedTags = () => {
    if (selectedTags.length === 0) return 'All tags';
    if (selectedTags.length === 1) return selectedTags[0];
    return `${selectedTags[0]}, ${selectedTags[1]}${selectedTags.length > 2 ? '...' : ''}`;
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="w-[150px] justify-between">
          <span className="truncate">
            {renderSelectedTags()}
          </span>
          <ChevronDownIcon className="h-4 w-4 flex-shrink-0" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onSelect={(e) => { e.preventDefault(); toggleTag('Tag 1'); }}>
          <input type="checkbox" checked={selectedTags.includes('Tag 1')} readOnly className="mr-2" />
          Tag 1
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={(e) => { e.preventDefault(); toggleTag('Tag 2'); }}>
          <input type="checkbox" checked={selectedTags.includes('Tag 2')} readOnly className="mr-2" />
          Tag 2
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={(e) => { e.preventDefault(); toggleTag('Tag 3'); }}>
          <input type="checkbox" checked={selectedTags.includes('Tag 3')} readOnly className="mr-2" />
          Tag 3
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const SortComponent = () => {
  const navigate = useNavigate()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">
          Sort <ChevronDownIcon className="ml-2 h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onClick={() => navigate({ to: '.', search: (prev) => ({ ...prev, sort: 'NAME_ASC' }) })}>
          A to Z
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => navigate({ to: '.', search: (prev) => ({ ...prev, sort: 'NAME_DESC' }) })}>
          Z to A
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default function FlowsTable({
  flows
}: {
  flows: components['schemas']['Flow'][] 
}) {

  const table = useReactTable({
    columns: columns,
    data: flows,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageIndex: 0,
        pageSize: 10,
      },
    },
  })

  return (
    <div className="h-full">
      <header className="mb-2 flex flex-row justify-between">
        <SearchComponent />
        <div className="flex space-x-4">
          <FilterComponent />
          <SortComponent />
        </div>
      </header>
        <DataTable table={table} />
    </div>
  )
}




