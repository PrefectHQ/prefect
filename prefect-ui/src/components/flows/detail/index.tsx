import { components } from '@/api/prefect';
import { useNavigate } from "@tanstack/react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DataTable } from '@/components/ui/data-table';
import { columns as flowRunColumns } from './runs-columns';
import { columns as deploymentColumns } from './deployment-columns';
import { columns  as metadataColumns, getFlowMetadata } from './metadata-columns';


import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDownIcon, SearchIcon } from 'lucide-react'
import {  getCoreRowModel,
  getPaginationRowModel,
  useReactTable, } from '@tanstack/react-table';

const SearchComponent = () => {
  const navigate = useNavigate()

  return <div className="relative">
    <Input placeholder="Run names" className="pl-10" onChange={(e) => navigate({ to:'.', search: (prev) => ({ ...prev, 'runs.flowRuns.nameLike': e.target.value }) })} />
    <SearchIcon className="absolute left-3 top-2.5 text-muted-foreground" size={18} />
  </div>
}

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
        <DropdownMenuItem onClick={() => navigate({'to': '.', 'search': (prev) => ({ ...prev, 'runs.sort': 'START_TIME_DESC' }) })}>
          Newest
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => navigate({'to': '.', 'search': (prev) => ({ ...prev, 'runs.sort': 'START_TIME_ASC' }) })}>
          Oldest
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default function FlowDetail({
    flow,
    flowRuns,
    activity, 
    deployments,
    tab = "runs"
}: {
    flow: components['schemas']['Flow'],
    flowRuns: components['schemas']['FlowRun'][],
    activity: components['schemas']['FlowRun'][],
    deployments: components['schemas']['DeploymentResponse'][],
    tab: "runs" | "deployments" | "details"
}): React.ReactElement {

  const navigate = useNavigate()
  console.log(activity)

  const flowRunTable = useReactTable({
    data: flowRuns,
    columns: flowRunColumns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageIndex: 0,
        pageSize: 10,
      },
    },
  })

  const deploymentsTable = useReactTable({
    data: deployments,
    columns: deploymentColumns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageIndex: 0,
        pageSize: 10,
      },
    },
  })

  const metadataTable = useReactTable({
    columns: metadataColumns,
    data: getFlowMetadata(flow),
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onPaginationChange: (pagination) => {
      console.log(pagination)
      return pagination
    },
    initialState: {
      pagination: {
        pageIndex: 0,
        pageSize: 10,
      },
    },
  })

  return (
    <div className="container mx-auto">

      <Tabs value={tab} onValueChange={(value) => navigate({to: '.', search: (prev) => ({ ...prev, tab: value as 'runs' | 'deployments' | 'details' }) })}>
        <TabsList>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="deployments">Deployments</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
        </TabsList>
        <TabsContent value="runs">
          <header className="mb-2 flex flex-row justify-between">
            <SearchComponent />
            <div className="flex space-x-4">
              {/* <FilterComponent /> */}
              <SortComponent />
            </div>
          </header>
          <DataTable table = {flowRunTable} />
        </TabsContent>
        <TabsContent value="deployments">
            <DataTable table = {deploymentsTable} />
        </TabsContent>
        <TabsContent value="details">
            <DataTable table = {metadataTable} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
