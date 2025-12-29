import type { OnChangeFn, PaginationState } from "@tanstack/react-table";
import {
	getCoreRowModel,
	type RowSelectionState,
	useReactTable,
} from "@tanstack/react-table";
import { Trash2 } from "lucide-react";
import type { ChangeEvent } from "react";
import { useCallback, useState } from "react";
import { useDeleteDeployment } from "@/api/deployments";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { FlowRunActivityBarGraphTooltipProvider } from "@/components/ui/flow-run-activity-bar-graph";
import { SearchInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { TagsInput } from "@/components/ui/tags-input";
import { Typography } from "@/components/ui/typography";
import { columns as baseDeploymentColumns } from "./deployment-columns";

type DeploymentSort = components["schemas"]["DeploymentSort"];

const SORT_OPTIONS: { label: string; value: DeploymentSort }[] = [
	{ label: "Created", value: "CREATED_DESC" },
	{ label: "A to Z", value: "NAME_ASC" },
	{ label: "Z to A", value: "NAME_DESC" },
];

type FlowDeploymentsTabProps = {
	deployments: components["schemas"]["DeploymentResponse"][];
	deploymentsCount: number;
	deploymentsPages: number;
	deploymentSearch: string | undefined;
	onDeploymentSearchChange: (search: string) => void;
	deploymentTags: string[];
	onDeploymentTagsChange: (tags: string[]) => void;
	deploymentSort: DeploymentSort;
	onDeploymentSortChange: (sort: DeploymentSort) => void;
	deploymentPagination: { page: number; limit: number };
	onDeploymentPaginationChange: (pagination: {
		page: number;
		limit: number;
	}) => void;
};

export const FlowDeploymentsTab = ({
	deployments,
	deploymentsCount,
	deploymentsPages,
	deploymentSearch,
	onDeploymentSearchChange,
	deploymentTags,
	onDeploymentTagsChange,
	deploymentSort,
	onDeploymentSortChange,
	deploymentPagination,
	onDeploymentPaginationChange,
}: FlowDeploymentsTabProps) => {
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const { deleteDeployment } = useDeleteDeployment();

	const handlePaginationChange: OnChangeFn<PaginationState> = useCallback(
		(updater) => {
			const currentPagination: PaginationState = {
				pageIndex: deploymentPagination.page - 1,
				pageSize: deploymentPagination.limit,
			};
			const newPagination =
				typeof updater === "function" ? updater(currentPagination) : updater;
			onDeploymentPaginationChange({
				page: newPagination.pageIndex + 1,
				limit: newPagination.pageSize,
			});
			setRowSelection({});
		},
		[deploymentPagination, onDeploymentPaginationChange],
	);

	const deploymentsTable = useReactTable({
		data: deployments,
		columns: baseDeploymentColumns,
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		pageCount: deploymentsPages,
		state: {
			rowSelection,
			pagination: {
				pageIndex: deploymentPagination.page - 1,
				pageSize: deploymentPagination.limit,
			},
		},
		onRowSelectionChange: setRowSelection,
		onPaginationChange: handlePaginationChange,
		getRowId: (row) => row.id,
	});

	const selectedCount = Object.keys(rowSelection).length;

	const handleDeleteSelected = useCallback(() => {
		const selectedIds = Object.keys(rowSelection);
		for (const id of selectedIds) {
			deleteDeployment(id);
		}
		setRowSelection({});
		setShowDeleteDialog(false);
	}, [rowSelection, deleteDeployment]);

	const handleDeploymentTagsChange: React.ChangeEventHandler<HTMLInputElement> &
		((tags: string[]) => void) = useCallback(
		(e: string[] | ChangeEvent<HTMLInputElement>) => {
			if (Array.isArray(e)) {
				onDeploymentTagsChange(e);
			}
		},
		[onDeploymentTagsChange],
	);

	return (
		<div className="flex flex-col gap-4">
			<div className="grid grid-cols-12 items-center gap-2">
				{/* Count and selection info - first column */}
				<div className="flex flex-col gap-1 xl:col-span-3 md:col-span-12 col-span-6 md:order-0 order-3">
					{selectedCount > 0 ? (
						<div className="flex items-center gap-2">
							<Typography variant="bodySmall" className="text-muted-foreground">
								{selectedCount} selected
							</Typography>
							<Button
								variant="ghost"
								size="icon"
								className="h-6 w-6 text-destructive hover:text-destructive"
								onClick={() => setShowDeleteDialog(true)}
								aria-label="Delete selected deployments"
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						</div>
					) : (
						<Typography variant="bodySmall" className="text-muted-foreground">
							{deploymentsCount} Deployment{deploymentsCount !== 1 ? "s" : ""}
						</Typography>
					)}
				</div>

				{/* Controls - middle columns */}
				<div className="xl:col-span-4 md:col-span-6 col-span-12 md:order-1 order-0">
					<SearchInput
						placeholder="Search deployments..."
						value={deploymentSearch ?? ""}
						onChange={(e) => onDeploymentSearchChange(e.target.value)}
						aria-label="Search deployments"
						debounceMs={300}
					/>
				</div>
				<div className="xl:col-span-3 md:col-span-6 col-span-12 md:order-2 order-1">
					<TagsInput
						placeholder="Filter by tags"
						value={deploymentTags}
						onChange={handleDeploymentTagsChange}
					/>
				</div>

				{/* Sort - last column with left border on desktop */}
				<div className="xl:border-l xl:border-border xl:pl-2 xl:col-span-2 md:col-span-6 col-span-6 md:order-3 order-2">
					<Select
						value={deploymentSort}
						onValueChange={(value) =>
							onDeploymentSortChange(value as DeploymentSort)
						}
					>
						<SelectTrigger className="w-full" aria-label="Sort deployments">
							<SelectValue placeholder="Sort by" />
						</SelectTrigger>
						<SelectContent>
							{SORT_OPTIONS.map((option) => (
								<SelectItem key={option.value} value={option.value}>
									{option.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
			</div>

			<FlowRunActivityBarGraphTooltipProvider>
				{/* Override table container overflow to allow chart tooltips to escape */}
				<div className="[&_[data-slot=table-container]]:overflow-visible">
					<DataTable table={deploymentsTable} />
				</div>
			</FlowRunActivityBarGraphTooltipProvider>

			<Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Delete Deployments</DialogTitle>
						<DialogDescription>
							Are you sure you want to delete {selectedCount} deployment
							{selectedCount !== 1 ? "s" : ""}? This action cannot be undone.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => setShowDeleteDialog(false)}
						>
							Cancel
						</Button>
						<Button variant="destructive" onClick={handleDeleteSelected}>
							Delete
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
};
