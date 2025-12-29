import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";

export function FlowRunNotFound() {
	return (
		<EmptyState>
			<EmptyStateIcon id="Search" />
			<EmptyStateTitle>Flow Run Not Found</EmptyStateTitle>
			<EmptyStateDescription>
				The flow run you are looking for does not exist or has been deleted.
			</EmptyStateDescription>
			<EmptyStateActions>
				<Button asChild>
					<Link to="/runs">Back to Runs</Link>
				</Button>
			</EmptyStateActions>
		</EmptyState>
	);
}
