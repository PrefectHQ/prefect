import { CodeBanner } from "@/components/code-banner";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { cn } from "@/utils";

export type WorkersTableEmptyStateProps = {
	hasSearchQuery: boolean;
	workPoolName: string;
	className?: string;
};

export const WorkersTableEmptyState = ({
	hasSearchQuery,
	workPoolName,
	className,
}: WorkersTableEmptyStateProps) => {
	if (hasSearchQuery) {
		return (
			<EmptyState>
				<EmptyStateIcon id="Search" />
				<EmptyStateTitle>No workers found</EmptyStateTitle>
				<EmptyStateDescription>
					No workers match your search criteria.
				</EmptyStateDescription>
			</EmptyState>
		);
	}

	return (
		<div className={cn("space-y-4", className)}>
			<EmptyState>
				<EmptyStateIcon id="Bot" />
				<EmptyStateTitle>No workers running</EmptyStateTitle>
				<EmptyStateDescription>
					No workers are currently running for the &ldquo;{workPoolName}&rdquo;
					work pool.
				</EmptyStateDescription>
				<EmptyStateActions>
					<CodeBanner
						command={`prefect worker start --pool "${workPoolName}"`}
						title="Start a worker"
						subtitle="Run this command to start a worker for this pool"
					/>
				</EmptyStateActions>
			</EmptyState>
		</div>
	);
};
