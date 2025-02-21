import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";
import { use } from "react";

import { RowSelectionContext } from "./row-selection-context";
import { useDeleteFlowRunsDialog } from "./use-delete-flow-runs-dialog";

export type FlowRunsRowCountProps = {
	flowRunsCount: number | undefined;
};

export const FlowRunsRowCount = ({ flowRunsCount }: FlowRunsRowCountProps) => {
	const rowSelectionCtx = use(RowSelectionContext);
	if (!rowSelectionCtx) {
		throw new Error(
			"'FlowRunsFilters' must be a child of `RowSelectionContext`",
		);
	}
	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteFlowRunsDialog();

	const selectedRows = Object.keys(rowSelectionCtx.rowSelection);

	if (selectedRows.length > 0) {
		return (
			<>
				<div className="flex items-center gap-1">
					<Typography variant="bodySmall" className="text-muted-foreground">
						{selectedRows.length} selected
					</Typography>
					<Button
						aria-label="Delete rows"
						size="icon"
						variant="secondary"
						onClick={() => {
							confirmDelete(selectedRows, () =>
								rowSelectionCtx.setRowSelection({}),
							);
						}}
					>
						<Icon id="Trash2" className="h-4 w-4" />
					</Button>
				</div>
				<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
			</>
		);
	}

	if (flowRunsCount === undefined) {
		return null;
	}

	return (
		<Typography variant="bodySmall" className="text-muted-foreground">
			{flowRunsCount} {pluralize(flowRunsCount, "Flow run")}
		</Typography>
	);
};
