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

type VariablesEmptyStateProps = {
	onAddVariableClick: () => void;
};
export const VariablesEmptyState = ({
	onAddVariableClick,
}: VariablesEmptyStateProps) => (
	<EmptyState>
		<EmptyStateIcon id="Variable" />
		<EmptyStateTitle>Add a variable to get started</EmptyStateTitle>
		<EmptyStateDescription>
			Variables store non-sensitive pieces of JSON.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button onClick={() => onAddVariableClick()}>
				Add Variable <Icon id="Plus" className="size-4 ml-2" />
			</Button>
			<DocsLink id="variables-guide" />
		</EmptyStateActions>
	</EmptyState>
);
