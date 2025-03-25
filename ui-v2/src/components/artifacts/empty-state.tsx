import { DocsLink } from "@/components/ui/docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";

export const ArtifactsEmptyState = () => (
	<EmptyState>
		<div className="flex items-center gap-3">
			<EmptyStateIcon id="Image" />
		</div>
		<EmptyStateTitle>Create an artifact to get started</EmptyStateTitle>
		<EmptyStateDescription>
			Artifacts are byproducts of your runs; they can be anything from a
			markdown string to a table.
		</EmptyStateDescription>
		<EmptyStateActions>
			<DocsLink id="artifacts-guide" />
		</EmptyStateActions>
	</EmptyState>
);
