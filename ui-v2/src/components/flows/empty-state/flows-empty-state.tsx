import { DocsLink } from "@/components/ui/docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";

export const FlowsEmptyState = () => (
	<EmptyState>
		<EmptyStateIcon id="Workflow" />
		<EmptyStateTitle>Run a flow to get started</EmptyStateTitle>
		<EmptyStateDescription>
			Flows are Python functions that encapsulate workflow logic and allow users
			to interact with and reason about the state of their workflows.
		</EmptyStateDescription>
		<EmptyStateActions>
			<DocsLink id="flows-guide" />
		</EmptyStateActions>
	</EmptyState>
);
