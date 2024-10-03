"use client"

import { useState } from 'react'
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  SortingState,
} from '@tanstack/react-table'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { CheckIcon, XIcon, ChevronDownIcon, MoreVerticalIcon, SearchIcon } from 'lucide-react'
import { components } from '@/api/prefect'


interface FlowRow {
  id: string
  name: string
  createdDate: string
  lastRun: { status: 'success' | 'failure'; name: string }
  nextRun: string | null
  deployments: number
  activity: number[]
}

const mockFlows: FlowRow[] = [
  {
    id: '1',
    name: 'Production Deploy',
    createdDate: '2023-05-15',
    lastRun: { status: 'success', name: 'deploy-123' },
    nextRun: null,
    deployments: 5,
    activity: [0.6, 0.3, 0.1],
  },
  {
    id: '2',
    name: 'Staging Build',
    createdDate: '2023-06-01',
    lastRun: { status: 'failure', name: 'build-456' },
    nextRun: '2023-07-01',
    deployments: 0,
    activity: [0.8, 0.2, 0],
  },
  {
    id: '3',
    name: 'Development Test',
    createdDate: '2023-06-15',
    lastRun: { status: 'success', name: 'test-789' },
    nextRun: '2023-07-02',
    deployments: 3,
    activity: [0.9, 0.05, 0.05],
  },
]

  const columns: ColumnDef<FlowRow>[] = [
    {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
      enableSorting: false,
      enableHiding: false,
    },
    {
      accessorKey: "name",
      header: "NAME",
      cell: ({ row }) => (
        <div>
          <div className="text-primary hover:underline cursor-pointer">{row.original.name}</div>
          <div className="text-sm text-muted-foreground">Created {row.original.createdDate}</div>
        </div>
      ),
    },
    {
      accessorKey: "lastRun",
      header: "LAST RUN",
      cell: ({ row }) => (
        <div className={`flex items-center ${row.original.lastRun.status === 'success' ? 'text-green-500' : 'text-red-500'}`}>
          {row.original.lastRun.status === 'success' ? (
            <CheckIcon size={16} className="mr-2" />
          ) : (
            <XIcon size={16} className="mr-2" />
          )}
          {row.original.lastRun.name}
        </div>
      ),
    },
    {
      accessorKey: "nextRun",
      header: "NEXT RUN",
      cell: ({ row }) => row.original.nextRun || 'None',
    },
    {
      accessorKey: "deployments",
      header: "DEPLOYMENTS",
      cell: ({ row }) => (
        row.original.deployments > 0 ? (
          <span className="text-primary hover:underline cursor-pointer">{row.original.deployments}</span>
        ) : (
          <span className="text-muted-foreground">None</span>
        )
      ),
    },
    {
      accessorKey: "activity",
      header: "ACTIVITY",
      cell: ({ row }) => (
        <div className="w-24 h-2 bg-secondary rounded-full overflow-hidden flex">
          {row.original.activity.map((value, index) => (
            <div
              key={index}
              style={{ width: `${value * 100}%` }}
              className={`h-full ${
                index === 0 ? 'bg-green-500' : index === 1 ? 'bg-red-500' : 'bg-orange-500'
              }`}
            />
          ))}
        </div>
      ),
    },
    {
      id: "actions",
      cell: ({ row }) => {
        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0">
                <span className="sr-only">Open menu</span>
                <MoreVerticalIcon className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => navigator.clipboard.writeText(row.original.id)}>
                Copy ID
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem>Delete</DropdownMenuItem>
              <DropdownMenuItem>Automate</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )
      },
    },
  ]

export default function Component({
    flows}: {
    flows: components['schemas']['Flow'][]
}) {
  const [flowList] = useState<FlowRow[]>(mockFlows)
  const [rowSelection, setRowSelection] = useState({})
  const [sorting, setSorting] = useState<SortingState>([])


  const table = useReactTable({
    data: flowList,
    columns,
    state: {
      sorting,
      rowSelection,
    },
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="h-full">
      <header className="mb-6 flex flex-row justify-between">
        <h1 className="flex self-center">{flowList.length} Flows</h1>
        <div className="flex space-x-4">
          <div className="relative">
            <Input placeholder="Flow names" className="pl-10" />
            <SearchIcon className="absolute left-3 top-2.5 text-muted-foreground" size={18} />
          </div>
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
        </div>
      </header>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}