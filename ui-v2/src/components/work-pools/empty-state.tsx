import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { DocsLink } from "@/components/ui/docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icons";

export const WorkPoolsEmptyState = () => (
	<EmptyState>
		<EmptyStateIcon id="Cpu" />
		<EmptyStateTitle>Add a work pool to get started</EmptyStateTitle>
		<EmptyStateDescription>
			Work pools allow you to prioritize and manage deployments and control the
			infrastructure they run on.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Link to="/work-pools/create">
				<Button>
					Add Work Pool <Icon id="Plus" className="size-4 ml-2" />
				</Button>
			</Link>
			<DocsLink id="work-pools-guide" />
		</EmptyStateActions>
	</EmptyState>
);
