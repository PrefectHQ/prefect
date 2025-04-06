import type { RowSelectionState } from "@tanstack/react-table";
import { useMemo } from "react";
import { Icon } from "../ui/icons";
import { Typography } from "../ui/typography";

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
			<Typography
				variant="bodySmall"
				className="text-muted-foreground flex items-center"
				fontFamily="mono"
			>
				{selectedRows.length} selected{" "}
				<Icon
					id="Trash2"
					className="m-1 ml-2 cursor-pointer h-4 w-4 inline"
					onClick={handleDeleteRows}
				/>
			</Typography>
		);
	}

	return (
		<Typography
			variant="bodySmall"
			className="text-muted-foreground"
			fontFamily="mono"
		>
			{count} Flows
		</Typography>
	);
};
