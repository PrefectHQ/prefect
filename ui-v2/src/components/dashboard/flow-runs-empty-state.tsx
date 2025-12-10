import type { JSX } from "react";

import { DocsLink } from "@/components/ui/docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";

export const DashboardFlowRunsEmptyState = (): JSX.Element => (
	<EmptyState>
		<EmptyStateIcon id="Workflow" />
		<EmptyStateTitle>Run a task or flow to get started</EmptyStateTitle>
		<EmptyStateDescription>
			Runs store the state history for each execution of a task or flow.
		</EmptyStateDescription>
		<EmptyStateActions>
			<DocsLink id="getting-started" />
		</EmptyStateActions>
	</EmptyState>
);
