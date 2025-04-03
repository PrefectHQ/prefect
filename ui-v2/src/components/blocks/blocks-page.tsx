import {
	buildCountFilterBlockDocumentsQuery,
	buildListFilterBlockDocumentsQuery,
} from "@/api/block-documents";
import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { RowSelectionState } from "@tanstack/react-table";
import { useState } from "react";
import { BlockDocumentsDataTable } from "./block-document-data-table";
import { BlocksEmptyState } from "./empty-state";
import { useDeleteBlockDocumentConfirmationDialog } from "./use-delete-block-document-confirmation-dialog";

export const BlocksPage = () => {
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

	const [dialogState, handleConfirmDelete] =
		useDeleteBlockDocumentConfirmationDialog();

	const { data: blockDocuments } = useSuspenseQuery(
		buildListFilterBlockDocumentsQuery(),
	);
	const { data: allBlockkDocumentsCount } = useSuspenseQuery(
		buildCountFilterBlockDocumentsQuery(),
	);

	return (
		<>
			<div className="flex flex-col gap-4">
				<BlocksPageHeader />
				{allBlockkDocumentsCount === 0 ? (
					<BlocksEmptyState />
				) : (
					<BlockDocumentsDataTable
						blockDocuments={blockDocuments}
						rowSelection={rowSelection}
						setRowSelection={setRowSelection}
						blockDocumentsCount={allBlockkDocumentsCount}
						pageCount={0}
						pagination={{
							pageIndex: 0,
							pageSize: 10,
						}}
						onPaginationChange={() => {
							/** TODO */
						}}
						onDelete={() => handleConfirmDelete(Object.keys(rowSelection))}
					/>
				)}
			</div>
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};

function BlocksPageHeader() {
	return (
		<div className="flex gap-2 items-center">
			<Typography className="font-semibold">Blocks</Typography>
			<Link to="/blocks/catalog">
				<Button
					size="icon"
					className="size-7"
					variant="outline"
					aria-label="add block document"
				>
					<Icon id="Plus" className="size-4" />
				</Button>
			</Link>
		</div>
	);
}
