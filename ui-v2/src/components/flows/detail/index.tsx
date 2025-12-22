import { useNavigate } from "@tanstack/react-router";
import {
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { subWeeks } from "date-fns";
import { type JSX, useCallback, useMemo, useState } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import useDebounce from "@/hooks/use-debounce";
import { DeleteFlowDialog } from "./delete-flow-dialog";
import { columns as deploymentColumns } from "./deployment-columns";
import { FlowPageHeader } from "./flow-page-header";
import {
	getFlowMetadata,
	columns as metadataColumns,
} from "./metadata-columns";
import { columns as flowRunColumns } from "./runs-columns";
import { FlowDetailStateFilter } from "./state-filter";

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

const BAR_WIDTH = 8;
const BAR_GAP = 4;

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
	const [numberOfBars, setNumberOfBars] = useState<number>(0);
	const debouncedNumberOfBars = useDebounce(numberOfBars, 150);

	const chartRef = useCallback((node: HTMLDivElement | null) => {
		if (!node) return;

		const updateBars = () => {
			const chartWidth = node.getBoundingClientRect().width;
			setNumberOfBars(Math.floor(chartWidth / (BAR_WIDTH + BAR_GAP)));
		};

		updateBars();
		const resizeObserver = new ResizeObserver(updateBars);
		resizeObserver.observe(node);
		return () => resizeObserver.disconnect();
	}, []);

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

	// Calculate date range for the chart (last 7 days)
	const { startDate, endDate } = useMemo((): {
		startDate: Date;
		endDate: Date;
	} => {
		const now = new Date();
		return {
			startDate: subWeeks(now, 1),
			endDate: now,
		};
	}, []);

	// Use debounced value if available, otherwise use immediate value
	const effectiveNumberOfBars = debouncedNumberOfBars || numberOfBars;

	return (
		<>
			<div className="container mx-auto">
				<FlowPageHeader
					flow={flow}
					onDelete={() => setShowDeleteDialog(true)}
				/>
				<div className="mb-2 w-full" ref={chartRef}>
					{effectiveNumberOfBars === 0 ? (
						<Skeleton className="h-48 w-full" />
					) : (
						<FlowRunActivityBarGraphTooltipProvider>
							<FlowRunActivityBarChart
								enrichedFlowRuns={enrichedFlowRuns}
								startDate={startDate}
								endDate={endDate}
								numberOfBars={effectiveNumberOfBars}
								barWidth={BAR_WIDTH}
								className="h-48 w-full"
							/>
						</FlowRunActivityBarGraphTooltipProvider>
					)}
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
								<FlowDetailStateFilter />
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
