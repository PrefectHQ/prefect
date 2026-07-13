import { Link, useNavigate } from "@tanstack/react-router";
import type {
	ColumnFiltersState,
	ColumnSizingState,
	OnChangeFn,
	PaginationState,
} from "@tanstack/react-table";
import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useCallback } from "react";
import type { DeploymentWithFlow } from "@/api/deployments";
import type { components } from "@/api/prefect";
import { useDeleteDeploymentConfirmationDialog } from "@/components/deployments/use-delete-deployment-confirmation-dialog";
import { FlowIconText } from "@/components/flows/flow-icon-text";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { FlowRunActivityBarGraphTooltipProvider } from "@/components/ui/flow-run-activity-bar-graph";
import { SearchInput } from "@/components/ui/input";
import { ScheduleBadgeGroup } from "@/components/ui/schedule-badge";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { StatusBadge } from "@/components/ui/status-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { TagsInput } from "@/components/ui/tags-input";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { pluralize } from "@/utils";
import { ActionsCell, ActivityCell } from "./cells";

export type DeploymentsDataTableProps = {
	deployments: DeploymentWithFlow[];
	currentDeploymentsCount: number;
	pageCount: number;
	pagination: PaginationState;
	sort: components["schemas"]["DeploymentSort"];
	columnFilters: ColumnFiltersState;
	onPaginationChange: (pagination: PaginationState) => void;
	onSortChange: (sort: components["schemas"]["DeploymentSort"]) => void;
	onColumnFiltersChange: (columnFilters: ColumnFiltersState) => void;
	filteredCount?: number;
	isPending?: boolean;
	isPlaceholderData?: boolean;
	onClearFilters?: () => void;
};

const columnHelper = createColumnHelper<DeploymentWithFlow>();

const createColumns = ({
	onDelete,
}: {
	onDelete: (deployment: DeploymentWithFlow) => void;
}) => [
	columnHelper.display({
		id: "name",
		header: "Deployment",
		cell: ({ row }) => (
			<div className="flex flex-col">
				<Link to="/deployments/deployment/$id" params={{ id: row.original.id }}>
					<span
						className="text-sm font-medium truncate text-link hover:text-link-hover"
						title={row.original.name}
					>
						{row.original.name}
					</span>
				</Link>

				{row.original.flow && (
					<FlowIconText
						flow={row.original.flow}
						className="text-xs text-muted-foreground flex items-center gap-1"
						iconSize={12}
					/>
				)}
			</div>
		),
		size: 200,
		minSize: 120,
	}),
	columnHelper.accessor("status", {
		id: "status",
		header: "Status",
		cell: ({ row }) => {
			const status = row.original.status;
			if (!status) return null;
			return (
				<div className="min-w-28">
					<StatusBadge status={status} />
				</div>
			);
		},
		size: 120,
		minSize: 100,
	}),
	columnHelper.display({
		id: "activity",
		header: "Activity",
		cell: (props) => (
			<div className="flex flex-row gap-2 items-center min-w-28">
				<ActivityCell {...props} />
			</div>
		),
		enableResizing: false,
		size: 300,
		minSize: 160,
	}),
	columnHelper.display({
		id: "tags",
		header: () => null,
		cell: ({ row }) => <TagBadgeGroup tags={row.original.tags ?? []} />,
		size: 160,
		minSize: 100,
	}),
	columnHelper.display({
		id: "schedules",
		header: "Schedules",
		cell: ({ row }) => {
			const schedules = row.original.schedules;
			if (!schedules || schedules.length === 0) return null;
			return <ScheduleBadgeGroup schedules={schedules} />;
		},
		size: 180,
		minSize: 120,
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => <ActionsCell {...props} onDelete={onDelete} />,
		enableResizing: false,
		size: 60,
	}),
];

const COLUMN_SIZING_STORAGE_KEY = "deployments-table-column-sizing";

export const DeploymentsDataTable = ({
	deployments,
	currentDeploymentsCount,
	pagination,
	pageCount,
	sort,
	columnFilters,
	onPaginationChange,
	onSortChange,
	onColumnFiltersChange,
	filteredCount: filteredCountProp,
	isPending = false,
	isPlaceholderData = false,
	onClearFilters,
}: DeploymentsDataTableProps) => {
	const filteredCount = filteredCountProp ?? deployments.length;
	const showFilteredEmptyState =
		filteredCount === 0 &&
		!isPending &&
		!isPlaceholderData &&
		Boolean(onClearFilters);
	const navigate = useNavigate();
	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteDeploymentConfirmationDialog();

	const nameSearchValue = (columnFilters.find(
		(filter) => filter.id === "flowOrDeploymentName",
	)?.value ?? "") as string;
	const tagsSearchValue = (columnFilters.find((filter) => filter.id === "tags")
		?.value ?? []) as string[];

	const handleNameSearchChange = useCallback(
		(value?: string) => {
			const filters = columnFilters.filter(
				(filter) => filter.id !== "flowOrDeploymentName",
			);
			onColumnFiltersChange(
				value ? [...filters, { id: "flowOrDeploymentName", value }] : filters,
			);
		},
		[onColumnFiltersChange, columnFilters],
	);

	const handleTagsSearchChange: React.ChangeEventHandler<HTMLInputElement> &
		((tags: string[]) => void) = useCallback(
		(e: string[] | React.ChangeEvent<HTMLInputElement>) => {
			const tags = Array.isArray(e) ? e : e.target.value;
			const filters = columnFilters.filter((filter) => filter.id !== "tags");
			onColumnFiltersChange(
				tags.length ? [...filters, { id: "tags", value: tags }] : filters,
			);
		},
		[onColumnFiltersChange, columnFilters],
	);

	const handlePaginationChange: OnChangeFn<PaginationState> = useCallback(
		(updater) => {
			const newPagination =
				typeof updater === "function" ? updater(pagination) : updater;
			onPaginationChange(newPagination);
		},
		[pagination, onPaginationChange],
	);

	const [columnSizing, setColumnSizing] = useLocalStorage<ColumnSizingState>(
		COLUMN_SIZING_STORAGE_KEY,
		{},
	);

	const handleColumnSizingChange: OnChangeFn<ColumnSizingState> = useCallback(
		(updater) => {
			setColumnSizing((prev) =>
				typeof updater === "function" ? updater(prev) : updater,
			);
		},
		[setColumnSizing],
	);

	const table = useReactTable({
		data: deployments,
		columns: createColumns({
			onDelete: (deployment) => {
				const name = deployment.flow?.name
					? `${deployment.flow?.name}/${deployment.name}`
					: deployment.name;
				confirmDelete({ ...deployment, name });
			},
		}),
		getCoreRowModel: getCoreRowModel(),
		pageCount,
		manualPagination: true,
		enableColumnResizing: true,
		columnResizeMode: "onChange",
		state: {
			pagination,
			columnSizing,
		},
		onPaginationChange: handlePaginationChange,
		onColumnSizingChange: handleColumnSizingChange,
	});
	return (
		<div>
			<div className="grid sm:grid-cols-2 md:grid-cols-12 gap-2 pb-4 items-center">
				<div className="sm:col-span-2 md:col-span-3 lg:col-span-4 md:order-first lg:order-first">
					<p className="text-sm text-muted-foreground">
						{currentDeploymentsCount.toLocaleString()}{" "}
						{pluralize(currentDeploymentsCount, "Deployment")}
					</p>
				</div>
				<div className="sm:col-span-2 md:col-span-3 lg:col-span-3">
					<SearchInput
						placeholder="Search deployments"
						value={nameSearchValue}
						onChange={(e) => handleNameSearchChange(e.target.value)}
					/>
				</div>
				<div className="sm:col-span-2 md:col-span-3 lg:col-span-3">
					<TagsInput
						placeholder="Filter by tags"
						onChange={handleTagsSearchChange}
						value={tagsSearchValue}
					/>
				</div>
				<div className="sm:col-span-2 md:col-span-3 lg:col-span-2">
					<Select value={sort} onValueChange={onSortChange}>
						<SelectTrigger
							aria-label="Deployment sort order"
							className="w-full"
						>
							<SelectValue placeholder="Sort by" />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value="CREATED_DESC">Created</SelectItem>
							<SelectItem value="UPDATED_DESC">Updated</SelectItem>
							<SelectItem value="NAME_ASC">A to Z</SelectItem>
							<SelectItem value="NAME_DESC">Z to A</SelectItem>
						</SelectContent>
					</Select>
				</div>
			</div>

			<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
			{showFilteredEmptyState ? (
				<DeploymentsFilteredEmptyState onClearFilters={onClearFilters} />
			) : (
				<FlowRunActivityBarGraphTooltipProvider>
					<DataTable
						table={table}
						onRowClick={(row) =>
							void navigate({
								to: "/deployments/deployment/$id",
								params: { id: row.id },
							})
						}
					/>
				</FlowRunActivityBarGraphTooltipProvider>
			)}
		</div>
	);
};

const DeploymentsFilteredEmptyState = ({
	onClearFilters,
}: {
	onClearFilters?: () => void;
}) => (
	<EmptyState>
		<EmptyStateIcon id="Search" />
		<EmptyStateTitle>No deployments match your filters</EmptyStateTitle>
		<EmptyStateDescription>
			Try adjusting your search or tag filters.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button variant="outline" onClick={onClearFilters}>
				Clear filters
			</Button>
		</EmptyStateActions>
	</EmptyState>
);
