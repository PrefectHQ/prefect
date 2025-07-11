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

export const BlocksEmptyState = () => (
	<EmptyState>
		<EmptyStateIcon id="Box" />
		<EmptyStateTitle>Add a block to get started</EmptyStateTitle>
		<EmptyStateDescription>
			Blocks securely store credentials and configuration to easily manage
			connections to external systems.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Link to="/blocks/catalog">
				<Button>
					Add Block <Icon id="Plus" className="size-4 ml-2" />
				</Button>
			</Link>
			<DocsLink id="blocks-guide" />
		</EmptyStateActions>
	</EmptyState>
);
