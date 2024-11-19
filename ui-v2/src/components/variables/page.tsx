import type { components } from "@/api/prefect";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { AddVariableDialog } from "@/components/variables/add-variable-dialog";
import { VariablesEmptyState } from "@/components/variables/empty-state";
import { PlusIcon } from "lucide-react";
import { useState } from "react";
import { VariablesDataTable } from "./data-table";
import type {
	ColumnFiltersState,
	OnChangeFn,
	PaginationState,
} from "@tanstack/react-table";

type VariablesPageProps = {
	variables: components["schemas"]["Variable"][];
	totalVariableCount: number;
	currentVariableCount: number;
	pagination: PaginationState;
	onPaginationChange: OnChangeFn<PaginationState>;
	columnFilters: ColumnFiltersState;
	onColumnFiltersChange: OnChangeFn<ColumnFiltersState>;
	sorting: components["schemas"]["VariableSort"];
	onSortingChange: (sortKey: components["schemas"]["VariableSort"]) => void;
};

export const VariablesPage = ({
	variables,
	totalVariableCount,
	currentVariableCount,
	pagination,
	onPaginationChange,
	columnFilters,
	onColumnFiltersChange,
	sorting,
	onSortingChange,
}: VariablesPageProps) => {
	const [addVariableDialogOpen, setAddVariableDialogOpen] = useState(false);
	const onAddVariableClick = () => {
		setAddVariableDialogOpen(true);
	};

	return (
		<>
			<AddVariableDialog
				open={addVariableDialogOpen}
				onOpenChange={setAddVariableDialogOpen}
			/>
			<div className="flex flex-col gap-4 p-4">
				<div className="flex items-center gap-2">
					<Breadcrumb>
						<BreadcrumbList>
							<BreadcrumbItem className="text-xl font-semibold">
								Variables
							</BreadcrumbItem>
						</BreadcrumbList>
					</Breadcrumb>
					<Button
						size="icon"
						className="h-7 w-7"
						variant="outline"
						onClick={onAddVariableClick}
					>
						<PlusIcon className="h-4 w-4" />
					</Button>
				</div>
				{totalVariableCount === 0 ? (
					<VariablesEmptyState onAddVariableClick={onAddVariableClick} />
				) : (
					<VariablesDataTable
						variables={variables}
						currentVariableCount={currentVariableCount}
						pagination={pagination}
						onPaginationChange={onPaginationChange}
						columnFilters={columnFilters}
						onColumnFiltersChange={onColumnFiltersChange}
						sorting={sorting}
						onSortingChange={onSortingChange}
					/>
				)}
			</div>
		</>
	);
};
