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

type GlobalConcurrencyLimitsEmptyStateProps = {
	onAdd: () => void;
};
export const GlobalConcurrencyLimitsEmptyState = ({
	onAdd,
}: GlobalConcurrencyLimitsEmptyStateProps) => (
	<EmptyState>
		<EmptyStateIcon id="AlignVerticalJustifyStart" />
		<EmptyStateTitle>Add a concurrency limit</EmptyStateTitle>
		<EmptyStateDescription>
			Global concurrency limits can be applied to flow runs, task runs and any
			operation where you want to control concurrency.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button onClick={onAdd}>
				Add Concurrency Limit <Icon id="Plus" className="size-4 ml-2" />
			</Button>
			<DocsLink id="global-concurrency-guide" />
		</EmptyStateActions>
	</EmptyState>
);
