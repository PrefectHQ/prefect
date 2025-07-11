import type { OnChangeFn, RowSelectionState } from "@tanstack/react-table";
import { useMemo } from "react";
import { useDeleteBlockDocumentConfirmationDialog } from "@/components/blocks/use-delete-block-document-confirmation-dialog";
import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";

export type BlocksRowCountProps = {
	count: number;
	rowSelection: RowSelectionState;
	setRowSelection: OnChangeFn<RowSelectionState>;
};
export const BlocksRowCount = ({
	count,
	rowSelection,
	setRowSelection,
}: BlocksRowCountProps) => {
	const [deleteConfirmationDialogState, handleConfirmDelete] =
		useDeleteBlockDocumentConfirmationDialog();

	const selectedBlockIds = useMemo(
		() => Object.keys(rowSelection),
		[rowSelection],
	);

	// If has selected rows
	if (selectedBlockIds.length > 0)
		return (
			<>
				<div className="flex items-center gap-2">
					<Typography variant="bodySmall" className="text-muted-foreground">
						{selectedBlockIds.length} selected
					</Typography>
					<Button
						aria-label="Delete rows"
						size="icon"
						variant="secondary"
						onClick={() => {
							handleConfirmDelete(selectedBlockIds, {
								onSuccess: () => setRowSelection({}),
							});
						}}
					>
						<Icon id="Trash2" className="size-4" />
					</Button>
				</div>
				<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
			</>
		);

	return (
		<Typography variant="bodySmall" className="text-muted-foreground">
			{count} {pluralize(count, "Block")}
		</Typography>
	);
};
