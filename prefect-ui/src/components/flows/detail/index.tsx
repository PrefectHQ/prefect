import { components } from '@/api/prefect';
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ChevronLeft, ChevronRight, MoreHorizontal, Search } from "lucide-react"
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { DataTable } from '@/components/ui/data-table';
import { columns as flowRunColumns } from './runs-columns';
import { columns as deploymentColumns } from './deployment-columns';
import { CalendarDatePicker } from '@/components/ui/calendar-date-picker';

const FlowGraph = () => (
  <Card>
    <CardHeader>
      <CardTitle>Flow Runs</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="border-2 border-dashed border-gray-300 rounded-md h-16"></div>
    </CardContent>
  </Card>
);

const TaskGraph = () => (
  <Card>
    <CardHeader>
      <CardTitle>Task Runs</CardTitle>
    </CardHeader>
    <CardContent>
      <p>0 Task Runs</p>
      <p>0 Completed</p>
    </CardContent>
  </Card>
);

export default ({
    flow,
    flowRuns,
    deployments
}: {
    flow: components['schemas']['Flow'],
    flowRuns: components['schemas']['FlowRun'][],
    deployments: components['schemas']['DeploymentResponse'][]
}) => {
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header Section */}
      <header className="mb-8">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to='/flows'>Flows</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{flow.name}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </header>

      {/* Summary and Filter Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <FlowGraph />
        <TaskGraph />
      </div>
      <div className="flex items-center justify-end mb-8">
        <CalendarDatePicker/>
      </div>

      {/* Tabbed Content Section */}
      <Tabs defaultValue="runs">
        <TabsList>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="deployments">Deployments</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
        </TabsList>

        <TabsContent value="runs">
            <DataTable columns = { flowRunColumns } data = {flowRuns}/>
          {/* <div className="space-y-4">
            <h2 className="text-xl font-semibold">11 Flow runs</h2>
            <div className="flex justify-between">
              <div className="flex space-x-2">
                <Input placeholder="Search by run name" className="w-64" />
                <Select>
                  <option>All run states</option>
                </Select>
                <Select>
                  <option>Newest to oldest</option>
                </Select>
              </div>
              <Button variant="outline" size="icon">
                <Search className="h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <Card key={i}>
                  <CardContent className="flex items-center justify-between p-4">
                    <div>
                      <p className="font-medium">a-new-flow &gt; quirky-condor</p>
                      <div className="text-sm text-gray-500">
                        <span>2 hours ago</span> • <span>0 parameters</span> • <span>3s</span> •{" "}
                        <span>1 Task run</span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded">
                        Completed
                      </span>
                      <Button variant="ghost" size="sm">
                        demo_deployment
                      </Button>
                      <Button variant="ghost" size="sm">
                        default-agent-pool
                      </Button>
                      <Button variant="ghost" size="sm">
                        default
                      </Button>
                      <Button variant="secondary" size="sm">
                        default-agent-pool
                      </Button>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div> */}
        </TabsContent>

        <TabsContent value="deployments">
          <DataTable columns = { deploymentColumns } data = {deployments}/>
        </TabsContent>

        <TabsContent value="details">
          <Card>
            <CardHeader>
              <CardTitle>Flow Metadata</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <dt className="font-medium text-gray-500">Flow ID</dt>
                  <dd className="mt-1">69e75b2f-2a09-4887-90d3-35f0a6cf3201</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-500">Created</dt>
                  <dd className="mt-1">2023-05-01 12:00:00 UTC</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-500">Updated</dt>
                  <dd className="mt-1">2023-05-02 15:30:00 UTC</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

