import type { RowSelectionState } from "@tanstack/react-table";
import { useMemo } from "react";
import { Icon } from "../ui/icons";

export type TableCountHeaderProps = {
	count: number;
	rowSelectionState: RowSelectionState;
	handleDeleteRows: () => void;
};

export const TableCountHeader = ({
	count,
	rowSelectionState,
	handleDeleteRows,
}: TableCountHeaderProps) => {
	const selectedRows = useMemo(
		() => Object.keys(rowSelectionState),
		[rowSelectionState],
	);

	if (selectedRows.length > 0) {
		return (
			<p className="text-sm text-muted-foreground flex items-center">
				{selectedRows.length} selected{" "}
				<Icon
					id="Trash2"
					className="m-1 ml-2 cursor-pointer h-4 w-4 inline"
					onClick={handleDeleteRows}
				/>
			</p>
		);
	}

	return (
		<p className="text-sm text-muted-foreground">
			{count.toLocaleString()} Flows
		</p>
	);
};
