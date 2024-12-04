import { Button } from "@/components/ui/button";
import { DocsLink } from "@/components/ui/docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { PlusIcon } from "lucide-react";

type Props = {
	onClick: () => void;
};
export const GlobalConcurrencyLimitEmptyState = ({ onClick }: Props) => (
	<EmptyState>
		<EmptyStateIcon id="AlignVerticalJustifyStart" />
		<EmptyStateTitle>Add a concurrency limit</EmptyStateTitle>
		<EmptyStateDescription>
			Global concurrency limits can be applied to flow runs, task runs and any
			operation where you want to control concurrency.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button onClick={onClick}>
				Add Concurrency Limit <PlusIcon className="h-4 w-4 ml-2" />
			</Button>
			<DocsLink id="global-concurrency-guide" />
		</EmptyStateActions>
	</EmptyState>
);
