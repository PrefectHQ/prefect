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
import type { OnChangeFn, PaginationState } from "@tanstack/react-table";

export const VariablesPage = ({
	variables,
	totalVariableCount,
	pagination,
	onPaginationChange,
}: {
	variables: components["schemas"]["Variable"][];
	totalVariableCount: number;
	pagination: PaginationState;
	onPaginationChange: OnChangeFn<PaginationState>;
}) => {
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
				{variables.length === 0 ? (
					<VariablesEmptyState onAddVariableClick={onAddVariableClick} />
				) : (
					<VariablesDataTable
						variables={variables}
						totalVariableCount={totalVariableCount}
						pagination={pagination}
						onPaginationChange={onPaginationChange}
					/>
				)}
			</div>
		</>
	);
};
