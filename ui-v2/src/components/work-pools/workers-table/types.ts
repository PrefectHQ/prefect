import type { WorkPoolWorker } from "@/api/work-pools";

export interface WorkersTableProps {
	workPoolName: string;
	className?: string;
}

export interface WorkersTableToolbarProps {
	searchQuery: string;
	onSearchChange: (query: string) => void;
	resultsCount: number;
	totalCount: number;
	className?: string;
}

export interface WorkersTableEmptyStateProps {
	hasSearchQuery: boolean;
	workPoolName: string;
	className?: string;
}

export interface WorkersTableRowActionsProps {
	worker: WorkPoolWorker;
	workPoolName: string;
}
