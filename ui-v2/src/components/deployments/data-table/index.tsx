import { Link } from "@tanstack/react-router";
import type {
	ColumnFiltersState,
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
import { DataTable } from "@/components/ui/data-table";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { FlowRunActivityBarGraphTooltipProvider } from "@/components/ui/flow-run-activity-bar-graph";
import { Icon } from "@/components/ui/icons";
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
						className="text-sm font-medium truncate"
						title={row.original.name}
					>
						{row.original.name}
					</span>
				</Link>

				{row.original.flow && (
					<Link to="/flows/flow/$id" params={{ id: row.original.flow_id }}>
						<span className="text-xs text-muted-foreground flex items-center gap-1">
							<Icon id="Workflow" size={12} />
							<span className="truncate" title={row.original.flow.name}>
								{row.original.flow.name}
							</span>
						</span>
					</Link>
				)}
			</div>
		),
		size: 100,
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
		size: 50,
	}),
	columnHelper.display({
		id: "activity",
		header: "Activity",
		cell: (props) => (
			<div className="flex flex-row gap-2 items-center min-w-28">
				<ActivityCell {...props} />
			</div>
		),
		size: 300,
	}),
	columnHelper.display({
		id: "tags",
		header: () => null,
		cell: ({ row }) => <TagBadgeGroup tags={row.original.tags ?? []} />,
	}),
	columnHelper.display({
		id: "schedules",
		header: "Schedules",
		cell: ({ row }) => {
			const schedules = row.original.schedules;
			if (!schedules || schedules.length === 0) return null;
			return <ScheduleBadgeGroup schedules={schedules} />;
		},
		size: 150,
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => <ActionsCell {...props} onDelete={onDelete} />,
	}),
];

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
}: DeploymentsDataTableProps) => {
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
			let newPagination = pagination;
			if (typeof updater === "function") {
				newPagination = updater(pagination);
			} else {
				newPagination = updater;
			}
			onPaginationChange(newPagination);
		},
		[pagination, onPaginationChange],
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
		defaultColumn: {
			maxSize: 300,
		},
		state: {
			pagination,
		},
		onPaginationChange: handlePaginationChange,
	});
	return (
		<div>
			<div className="grid sm:grid-cols-2 md:grid-cols-6 lg:grid-cols-12 gap-2 pb-4 items-center">
				<div className="sm:col-span-2 md:col-span-6 lg:col-span-4 order-last lg:order-first">
					<p className="text-sm text-muted-foreground">
						{currentDeploymentsCount}{" "}
						{pluralize(currentDeploymentsCount, "Deployment")}
					</p>
				</div>
				<div className="sm:col-span-2 md:col-span-2 lg:col-span-3">
					<SearchInput
						placeholder="Search deployments"
						value={nameSearchValue}
						onChange={(e) => handleNameSearchChange(e.target.value)}
					/>
				</div>
				<div className="xs:col-span-1 md:col-span-2 lg:col-span-3">
					<TagsInput
						placeholder="Filter by tags"
						onChange={handleTagsSearchChange}
						value={tagsSearchValue}
					/>
				</div>
				<div className="xs:col-span-1 md:col-span-2 lg:col-span-2">
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
			<FlowRunActivityBarGraphTooltipProvider>
				<DataTable table={table} />
			</FlowRunActivityBarGraphTooltipProvider>
		</div>
	);
};
