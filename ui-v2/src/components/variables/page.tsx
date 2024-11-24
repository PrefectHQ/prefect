import type { components } from "@/api/prefect";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import {
	VariableDialog,
	type VariableDialogProps,
} from "@/components/variables/variable-dialog";
import { VariablesEmptyState } from "@/components/variables/empty-state";
import { PlusIcon } from "lucide-react";
import { useCallback, useState } from "react";
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
	const [variableToEdit, setVariableToEdit] = useState<
		VariableDialogProps["existingVariable"] | undefined
	>(undefined);

	const onAddVariableClick = useCallback(() => {
		setVariableToEdit(undefined);
		setAddVariableDialogOpen(true);
	}, []);

	const handleVariableEdit = useCallback(
		(variable: components["schemas"]["Variable"]) => {
			setVariableToEdit(variable);
			setAddVariableDialogOpen(true);
		},
		[],
	);

	const handleVariableDialogOpenChange = useCallback((open: boolean) => {
		setAddVariableDialogOpen(open);
	}, []);

	return (
		<>
			<VariableDialog
				open={addVariableDialogOpen}
				onOpenChange={handleVariableDialogOpenChange}
				existingVariable={variableToEdit}
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
						onVariableEdit={handleVariableEdit}
					/>
				)}
			</div>
		</>
	);
};
