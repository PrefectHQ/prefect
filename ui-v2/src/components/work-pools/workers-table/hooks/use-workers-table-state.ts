import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import { useState } from "react";

export const useWorkersTableState = () => {
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 10,
	});

	const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

	return {
		pagination,
		columnFilters,
		onPaginationChange: setPagination,
		onColumnFiltersChange: setColumnFilters,
	};
};
