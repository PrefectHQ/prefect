import { useNavigate } from "@tanstack/react-router";
import {
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { type JSX, useState } from "react";
import type { FlowRun } from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	FlowRunActivityBarChart,
	FlowRunActivityBarGraphTooltipProvider,
} from "@/components/ui/flow-run-activity-bar-graph";
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DeleteFlowDialog } from "./delete-flow-dialog";
import { columns as deploymentColumns } from "./deployment-columns";
import { FlowPageHeader } from "./flow-page-header";
import {
	getFlowMetadata,
	columns as metadataColumns,
} from "./metadata-columns";
import { columns as flowRunColumns } from "./runs-columns";

const SearchComponent = () => {
	const navigate = useNavigate();

	return (
		<div className="relative">
			<Input
				placeholder="Run names"
				className="pl-10"
				onChange={(e) =>
					void navigate({
						to: ".",
						search: (prev) => ({
							...prev,
							"runs.flowRuns.nameLike": e.target.value,
						}),
					})
				}
			/>
			<Icon
				id="Search"
				className="absolute left-3 top-2.5 text-muted-foreground"
				size={18}
			/>
		</div>
	);
};

const SortComponent = () => {
	const navigate = useNavigate();

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="outline">
					Sort <Icon id="ChevronDown" className="ml-2 size-4" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent>
				<DropdownMenuItem
					onClick={() =>
						void navigate({
							to: ".",
							search: (prev) => ({ ...prev, "runs.sort": "START_TIME_DESC" }),
						})
					}
				>
					Newest
				</DropdownMenuItem>
				<DropdownMenuItem
					onClick={() =>
						void navigate({
							to: ".",
							search: (prev) => ({ ...prev, "runs.sort": "START_TIME_ASC" }),
						})
					}
				>
					Oldest
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};

export default function FlowDetail({
	flow,
	flowRuns,
	activity,
	deployments,
	tab = "runs",
}: {
	flow: Flow;
	flowRuns: FlowRun[];
	activity: FlowRun[];
	deployments: components["schemas"]["DeploymentResponse"][];
	tab: "runs" | "deployments" | "details";
}): JSX.Element {
	const navigate = useNavigate();
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);

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
	});

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
	});

	const metadataTable = useReactTable({
		columns: metadataColumns,
		data: getFlowMetadata(flow),
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		onPaginationChange: (pagination) => {
			console.log(pagination);
			return pagination;
		},
		initialState: {
			pagination: {
				pageIndex: 0,
				pageSize: 10,
			},
		},
	});

	// Enrich flow runs with flow object
	const enrichedFlowRuns = activity.map((flowRun) => ({
		...flowRun,
		flow: flow,
	}));

	return (
		<>
			<div className="container mx-auto">
				<FlowPageHeader
					flow={flow}
					onDelete={() => setShowDeleteDialog(true)}
				/>
				<div className="h-[200px] mb-2">
					<FlowRunActivityBarGraphTooltipProvider>
						<FlowRunActivityBarChart
							enrichedFlowRuns={enrichedFlowRuns}
							startDate={new Date(Date.now() - 1000 * 60 * 24 * 7)}
							endDate={new Date(Date.now())}
							numberOfBars={24}
							className="mb-2"
						/>
					</FlowRunActivityBarGraphTooltipProvider>
				</div>
				<Tabs
					value={tab}
					onValueChange={(value) =>
						void navigate({
							to: ".",
							search: (prev) => ({
								...prev,
								tab: value as "runs" | "deployments" | "details",
							}),
						})
					}
				>
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
						<DataTable table={flowRunTable} />
					</TabsContent>
					<TabsContent value="deployments">
						<DataTable table={deploymentsTable} />
					</TabsContent>
					<TabsContent value="details">
						<DataTable table={metadataTable} />
					</TabsContent>
				</Tabs>
			</div>
			<DeleteFlowDialog
				flow={flow}
				open={showDeleteDialog}
				onOpenChange={setShowDeleteDialog}
			/>
		</>
	);
}
