import { DocsLink } from "@/components/ui/docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";

export const DeploymentsEmptyState = () => (
	<EmptyState>
		<div className="flex items-center gap-3">
			<EmptyStateIcon id="Workflow" />
			<EmptyStateIcon id="MoreHorizontal" />
			<EmptyStateIcon id="Rocket" />
		</div>
		<EmptyStateTitle>Create a deployment to get started</EmptyStateTitle>
		<EmptyStateDescription>
			Deployments elevate workflows from functions you call manually to API
			objects that can be remotely triggered.
		</EmptyStateDescription>
		<EmptyStateActions>
			<DocsLink id="deployments-guide" />
		</EmptyStateActions>
	</EmptyState>
);
