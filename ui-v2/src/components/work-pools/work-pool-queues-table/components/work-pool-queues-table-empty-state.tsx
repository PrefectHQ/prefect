import {
	EmptyState,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";

type WorkPoolQueuesTableEmptyStateProps = {
	hasSearchQuery: boolean;
	workPoolName: string;
};

export const WorkPoolQueuesTableEmptyState = ({
	hasSearchQuery,
}: WorkPoolQueuesTableEmptyStateProps) => {
	if (hasSearchQuery) {
		return (
			<EmptyState>
				<EmptyStateIcon id="Search" />
				<EmptyStateTitle>No queues found</EmptyStateTitle>
				<EmptyStateDescription>
					No queues match your search criteria. Try adjusting your search.
				</EmptyStateDescription>
			</EmptyState>
		);
	}

	return (
		<EmptyState>
			<EmptyStateIcon id="ListTodo" />
			<EmptyStateTitle>No queues yet</EmptyStateTitle>
			<EmptyStateDescription>
				This work pool doesn&apos;t have any queues yet. Create your first queue
				to start organizing work.
			</EmptyStateDescription>
		</EmptyState>
	);
};
