import { RowSelectionState } from "@tanstack/react-table";
import { useState } from "react";

import { RowSelectionContext } from "./row-selection-context";

export const RowSelectionProvider = ({
	children,
}: { children: React.ReactNode }) => {
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

	return (
		<RowSelectionContext.Provider value={{ rowSelection, setRowSelection }}>
			{children}
		</RowSelectionContext.Provider>
	);
};
