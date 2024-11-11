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

export const VariablesPage = () => {
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
				<VariablesEmptyState onAddVariableClick={onAddVariableClick} />
			</div>
		</>
	);
};
