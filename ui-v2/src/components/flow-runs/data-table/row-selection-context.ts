import { OnChangeFn, RowSelectionState } from "@tanstack/react-table";
import { createContext } from "react";

export const RowSelectionContext = createContext<{
	rowSelection: RowSelectionState;
	setRowSelection: OnChangeFn<RowSelectionState>;
} | null>(null);
