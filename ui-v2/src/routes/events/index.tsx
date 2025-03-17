import { createFileRoute } from "@tanstack/react-router";
import { getQueryHooks } from "@/api/query";
import { readEventsEventsFilterPostBody } from "@/api/zod/events/events";
import { zodValidator } from "@tanstack/zod-adapter";
import { components } from "@/api/prefect";
import { Link } from "@tanstack/react-router";
import { formatISO } from "date-fns";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDownIcon } from "lucide-react";
import * as React from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	ChartConfig,
	ChartContainer,
	ChartTooltip,
	ChartTooltipContent,
} from "@/components/ui/chart";
import { subDays, endOfDay, addHours, startOfHour } from "date-fns";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import {
	ColumnDef,
	flexRender,
	getCoreRowModel,
	useReactTable,
	PaginationState,
} from "@tanstack/react-table";


const END_DATE = startOfHour(addHours(endOfDay(new Date()), 1)).toISOString();
const START_DATE = subDays(END_DATE, 7).toISOString();

export const Route = createFileRoute("/events/")({
	component: RouteComponent,
	validateSearch: zodValidator(readEventsEventsFilterPostBody),
	loaderDeps: ({ search }) => search,
	loader: async ({ context, deps }) => {
		return await Promise.all([
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/events/filter", {
					// Note: There's a type mismatch between deps and the API schema.
					// The API expects 'resource.distinct' to be a required boolean, but our schema defines it as optional.
					// This is an idiosyncrasy between orval and openapi-ts but is fine for now.
					body: deps as components["schemas"]["Body_read_events_events_filter_post"]
				})),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/events/count-by/{countable}", {
					params: {
						path: { countable: "time" }
					},
					body: {
						filter: {
							any_resource: deps.filter?.any_resource,
							order: "DESC",
							occurred: {
								since: START_DATE,
								until: END_DATE
							}
						},
						time_interval: 1,
						time_unit: "hour"
					}
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/flows/filter", {
					body: { offset: 0, sort: "CREATED_DESC" }
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/work_pools/filter", {
					body: { offset: 0, sort: "CREATED_DESC" }
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/deployments/filter", {
					body: { offset: 0, sort: "CREATED_DESC" }
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/block_documents/filter", {
					body: { offset: 0, sort: "NAME_ASC", include_secrets: false }
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/automations/filter", {
					body: { offset: 0, sort: "CREATED_DESC" }
				})
			),
		])
	},
});

function ResourceCheckboxItem({
	resourceType,
	resourceId,
}: {
	resourceType: string;
	resourceId: string;
	checked?: boolean;
}) {
	const { filter } = Route.useSearch();
	const navigate = Route.useNavigate();
	return (
		<DropdownMenuCheckboxItem
			key={resourceId}
			onSelect={(e) => e.preventDefault()}
			checked={filter?.any_resource?.id?.map(item => item.includes(resourceId)).includes(true)}
			onCheckedChange={(checked) => {navigate({
				to: "/events",
				search: (prev) => {		
					
					return {
						...prev,
						filter: {
							...prev.filter,
							any_resource: {'id': checked ? [...(prev?.filter?.any_resource?.id || []), resourceId] : prev?.filter?.any_resource?.id?.filter(item => item !== resourceId)
			}}}}})}}
		>
			{resourceType}
		</DropdownMenuCheckboxItem>
	);
}

function RouteComponent() {
	const [ events, eventGroupCounts, flows, workPools, deployments, blockDocuments, automations ]= Route.useLoaderData();
	const search = Route.useSearch();
	const navigate = Route.useNavigate();
	
	// Get selected resources from search params
	const resourceFilter = search.filter?.resource || {};
	const resourceIds = resourceFilter.id || [];
	const resourceArray = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
	
	const countSelected = () => {
		return resourceArray.length > 0 ? `${resourceArray.length} selected` : "Filter by resource";
	};
	

	const chartConfig = {
		events: {
			label: "Events",
			color: "hsl(var(--chart-1))",
		},
		count: {
			label: "Count",
			color: "hsl(var(--chart-1))",
		},
	} satisfies ChartConfig;
	
	const totalEvents = React.useMemo(() => 
		eventGroupCounts.reduce((acc, curr) => acc + curr.count, 0),
	[eventGroupCounts]);
	
	// Table pagination state
	const [pagination, setPagination] = React.useState<PaginationState>({
		pageIndex: search.offset ? Math.floor(search.offset / (search.limit || 10)) : 0,
		pageSize: search.limit || 10,
	});
	
	// Update URL when pagination changes
	React.useEffect(() => {
		navigate({
			to: "/events",
			search: (prev) => ({
				...prev,
				limit: pagination.pageSize,
				offset: pagination.pageIndex * pagination.pageSize,
			}),
			replace: true,
		});
	}, [pagination, navigate]);
	
	// Define table columns
	const columns = React.useMemo<ColumnDef<typeof events.events[0]>[]>(
		() => [

			{
				accessorKey: "occurred",
				header: "Time",
				cell: ({ row }) => {
					const date = new Date(row.original.occurred);
					return (
						<div title={date.toISOString()}>
							{date.toLocaleString("en-US", {
								month: "short",
								day: "numeric",
								year: "numeric",
								hour: "numeric",
								minute: "2-digit",
							})}
						</div>
					);
				},
			},
			{
				accessorKey: "event",
				header: "Event Type",
				cell: ({ row }) => <div>{row.original.event}</div>,
			},
			{
				accessorKey: "resource",
				header: "Resource",
				cell: ({ row }) => (
					<div>{row.original.resource?.["prefect.resource.name"] || "-"}</div>
				),
			},

		],
		[]
	);
	
	// Create table instance
	const table = useReactTable({
		data: events.events,
		columns,
		pageCount: Math.ceil(events.total / pagination.pageSize),
		state: {
			pagination,
		},
		onPaginationChange: setPagination,
		manualPagination: true,
		getCoreRowModel: getCoreRowModel(),
	});
	
	return (
		<div className="h-full max-h-full max-w-full">
			<div className="h-14 flex-0 space-x-4">
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="outline" className="w-[280px] justify-between">
							{countSelected()}
							<ChevronDownIcon className="ml-2 h-4 w-4" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent className="w-[280px]">
						{automations.length > 0 && (
							<>
								<DropdownMenuLabel>Automations</DropdownMenuLabel>
								<DropdownMenuGroup>
									{automations.map((automation) => (
										<ResourceCheckboxItem
											key={automation.id}
											resourceType={automation.name}
											resourceId={'prefect.automation.' + automation.id}
										/>
									))}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
							</>
						)}
						{blockDocuments.length > 0 && (
							<>
								<DropdownMenuLabel>Blocks</DropdownMenuLabel>
								<DropdownMenuGroup>
									{blockDocuments.map((blockDocument) => (
										<ResourceCheckboxItem
											key={blockDocument.id}
											resourceType={blockDocument.name || 'Unnamed Block'}
											resourceId={'prefect.block_document.' + blockDocument.id}
										/>
									))}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
							</>
						)}
						{deployments.length > 0 && (
							<>
								<DropdownMenuLabel>Deployments</DropdownMenuLabel>
								<DropdownMenuGroup>
									{deployments.map((deployment) => (
										<ResourceCheckboxItem
											key={deployment.id}
											resourceType={deployment.name}
											resourceId={'prefect.deployment.' + deployment.id}
										/>
									))}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
							</>
						)}
						{flows.length > 0 && (
							<>
								<DropdownMenuLabel>Flows</DropdownMenuLabel>
								<DropdownMenuGroup>
									{flows.map((flow) => (
										<ResourceCheckboxItem
											key={flow.id}
											resourceType={flow.name}
											resourceId={'prefect.flow.' + flow.id}
										/>
									))}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
							</>
						)}
						{workPools.length > 0 && (
							<>
								<DropdownMenuLabel>Work Pools</DropdownMenuLabel>
								<DropdownMenuGroup>
									{workPools.map((workPool) => (
										<ResourceCheckboxItem
											key={workPool.id}
											resourceType={workPool.name}
											resourceId={'prefect.work_pool.' + workPool.id}
										/>
									))}
								</DropdownMenuGroup>
							</>
						)}
					</DropdownMenuContent>
				</DropdownMenu>
				
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="outline" className="w-[280px] justify-between">
							{"Filter by event type"}
							<ChevronDownIcon className="ml-2 h-4 w-4" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent className="w-[280px]">
						<DropdownMenuLabel>Event Types</DropdownMenuLabel>
						{eventGroupCounts.map((label, index) => (
							<DropdownMenuCheckboxItem 
								key={index}
								onSelect={(e) => e.preventDefault()}
								checked={search.filter?.event?.name?.includes(label.label)}
								onCheckedChange={(checked) => {
									navigate({
										to: "/events",
										search: (prev) => {
											return {
												...prev,
												filter: {
													...prev.filter,
													event: {
														"name": checked ? [...(prev?.filter?.event?.name || []), label.label] : prev?.filter?.event?.name?.filter(item => item !== label.label)
													}
												}
											}
										},
										replace: true
									})
								}}
								>{label.label}</DropdownMenuCheckboxItem>
						
						))}
					</DropdownMenuContent>
				</DropdownMenu>
			</div>


			<Card className="h-[calc(100%-4rem)] max-h-full flex flex-col m-0 p-0 gap-0 rounded-b-none border-b-0">
				<CardHeader className="flex flex-col items-stretch space-y-0 border-b p-0 sm:flex-row flex-shrink-0">
					<div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5 sm:py-6">
						<CardTitle>Events Timeline</CardTitle>
						<CardDescription>
							Showing {totalEvents} events over time
						</CardDescription>
					</div>
					<div className="flex">
						<div className="relative z-30 flex flex-1 flex-col justify-center gap-1 border-t px-6 py-4 text-left data-[active=true]:bg-muted/50 sm:border-l sm:border-t-0 sm:px-8 sm:py-6">
							<span className="text-xs text-muted-foreground">
								{chartConfig.events.label}
							</span>
							<span className="text-lg font-bold leading-none sm:text-3xl">
								{totalEvents.toLocaleString()}
							</span>
						</div>
					</div>
				</CardHeader>
				<CardContent className="!p-0 sm:p-6 flex-1 flex flex-col min-h-0">
					<ChartContainer
						config={chartConfig}
						className="aspect-auto h-[250px] px-6 w-full mb-6 flex-shrink-0"
					>
						<BarChart
							accessibilityLayer
							data={eventGroupCounts}
							margin={{
								left: -36,
								right: 24,
							}}
						>
							<CartesianGrid vertical={false} />
							<XAxis
								dataKey="start_time"
								tickLine={false}
								axisLine={false}
								tickMargin={8}
								minTickGap={32}
								tickFormatter={(value) => {
									const date = new Date(value);
									return date.toLocaleString("en-US", {
										month: "short",
										day: "numeric",
										hour: "numeric",
										minute: "2-digit",
									});
								}}
							/>
							<YAxis />
							<ChartTooltip
								content={
									<ChartTooltipContent
										className="w-[200px]"
										nameKey="events"
										labelFormatter={(value) => {
											return new Date(value).toLocaleString("en-US", {
												month: "short",
												day: "numeric",
												year: "numeric",
												hour: "numeric",
												minute: "2-digit",
											});
										}}
									/>
								}
							/>
							<Bar dataKey="count" fill={chartConfig.count.color} />
						</BarChart>
					</ChartContainer>
					<div className="flex-1 h-full min-h-0">
						
						<div className="h-full max-h-full overflow-auto border-t">
						<Table className="h-full max-h-full">
						<TableHeader>
								{table.getHeaderGroups().map((headerGroup) => (
									<TableRow key={headerGroup.id}>
										{headerGroup.headers.map((header) => (
											<TableHead key={header.id} className="sticky top-0 z-10 bg-background">
												{header.isPlaceholder
													? null
													: flexRender(
														header.column.columnDef.header,
														header.getContext()
													)}
											</TableHead>
										))}
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
											No events found.
										</TableCell>
									</TableRow>
								)}
							</TableBody>
						</Table>
						</div>
		 			</div>

				</CardContent>
		 	</Card>

		 </div>
	);
}