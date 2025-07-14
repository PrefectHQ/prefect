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

export const AutomationsEmptyState = () => {
	return (
		<EmptyState>
			<EmptyStateIcon id="Bot" />
			<EmptyStateTitle>Create an automation to get started</EmptyStateTitle>
			<EmptyStateDescription>
				Automations bring reactivity to your data stack and let you configure
				triggers and actions based on events.
			</EmptyStateDescription>
			<EmptyStateActions>
				<Link to="/automations/create">
					<Button>
						Add Automation <Icon id="Plus" className="size-4 ml-2" />
					</Button>
				</Link>
				<DocsLink id="automations-guide" />
			</EmptyStateActions>
		</EmptyState>
	);
};
