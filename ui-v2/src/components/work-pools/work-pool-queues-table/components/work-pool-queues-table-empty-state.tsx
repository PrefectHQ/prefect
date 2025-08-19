import { Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";

type WorkPoolQueuesTableEmptyStateProps = {
	hasSearchQuery: boolean;
	workPoolName: string;
};

export const WorkPoolQueuesTableEmptyState = ({
	hasSearchQuery,
	workPoolName,
}: WorkPoolQueuesTableEmptyStateProps) => {
	if (hasSearchQuery) {
		return (
			<div className="flex flex-col items-center justify-center py-12 text-center">
				<Search className="h-12 w-12 text-muted-foreground mb-4" />
				<h3 className="text-lg font-medium text-foreground mb-2">
					No queues found
				</h3>
				<p className="text-muted-foreground mb-4">
					No queues match your search criteria. Try adjusting your search.
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-col items-center justify-center py-12 text-center">
			<div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
				<Plus className="h-6 w-6 text-muted-foreground" />
			</div>
			<h3 className="text-lg font-medium text-foreground mb-2">
				No queues yet
			</h3>
			<p className="text-muted-foreground mb-4 max-w-md">
				This work pool doesn&apos;t have any queues yet. Create your first queue
				to start organizing work.
			</p>
			<Button
				onClick={() => {
					// TODO: Navigate to create queue page when route exists
					console.log("Create queue for pool:", workPoolName);
				}}
			>
				<Plus className="h-4 w-4 mr-2" />
				Create Queue
			</Button>
		</div>
	);
};
