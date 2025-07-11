import type { CheckedState } from "@radix-ui/react-checkbox";
import {
	createColumnHelper,
	getCoreRowModel,
	type OnChangeFn,
	type PaginationState,
	type RowSelectionState,
	useReactTable,
} from "@tanstack/react-table";
import { useCallback } from "react";
import type { BlockDocument } from "@/api/block-documents";
import { BlockDocumentActionMenu } from "@/components/blocks/block-document-action-menu";
import { useDeleteBlockDocumentConfirmationDialog } from "@/components/blocks/use-delete-block-document-confirmation-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable } from "@/components/ui/data-table";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { BlockDocumentCell } from "./block-document-cell";

const columnHelper = createColumnHelper<BlockDocument>();

const createColumns = ({
	onDelete,
}: {
	onDelete: (blockDocument: BlockDocument) => void;
}) => [
	columnHelper.display({
		size: 20,
		id: "select",
		header: ({ table }) => {
			let checkedState: CheckedState = false;
			if (table.getIsAllRowsSelected()) {
				checkedState = true;
			} else if (table.getIsSomePageRowsSelected()) {
				checkedState = "indeterminate";
			}
			return (
				<Checkbox
					checked={checkedState}
					onCheckedChange={(value) =>
						table.toggleAllPageRowsSelected(Boolean(value))
					}
					aria-label="Select all"
				/>
			);
		},
		cell: ({ row }) => (
			<Checkbox
				checked={row.getIsSelected()}
				onCheckedChange={(value) => row.toggleSelected(Boolean(value))}
				aria-label="Select row"
			/>
		),
		enableSorting: false,
		enableHiding: false,
	}),
	columnHelper.display({
		id: "block",
		header: "Block",
		cell: ({ row }) => <BlockDocumentCell blockDocument={row.original} />,
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => {
			const cell = props.row.original;
			return (
				<div className="flex justify-end">
					<BlockDocumentActionMenu
						blockDocument={cell}
						onDelete={() => onDelete(cell)}
					/>
				</div>
			);
		},
	}),
];

export type BlockDocumentsDataTableProps = {
	blockDocumentsCount: number;
	blockDocuments: Array<BlockDocument>;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	rowSelection: RowSelectionState;
	setRowSelection: OnChangeFn<RowSelectionState>;
};
export const BlockDocumentsDataTable = ({
	blockDocuments,
	blockDocumentsCount,
	onPaginationChange,
	pagination,
	rowSelection,
	setRowSelection,
}: BlockDocumentsDataTableProps) => {
	const [dialogState, handleConfirmDelete] =
		useDeleteBlockDocumentConfirmationDialog();

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
		columns: createColumns({ onDelete: handleConfirmDelete }),
		data: blockDocuments,
		defaultColumn: { maxSize: 300 },
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		onPaginationChange: handlePaginationChange,
		rowCount: blockDocumentsCount,
		getRowId: (row) => row.id,
		onRowSelectionChange: setRowSelection,
		state: { pagination, rowSelection },
	});

	return (
		<>
			<DataTable table={table} />
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};
