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

type Props = {
	onAdd: () => void;
};
export const TaskRunConcurrencyLimitEmptyState = ({ onAdd }: Props) => (
	<EmptyState>
		<EmptyStateIcon id="CircleArrowOutUpRight" />
		<EmptyStateTitle>
			Add a concurrency limit for your task runs
		</EmptyStateTitle>
		<EmptyStateDescription>
			Creating a limit allows you to limit the number of tasks running
			simultaneously with a given tag.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button onClick={onAdd}>
				Add Concurrency Limit <Icon id="Plus" className="h-4 w-4 ml-2" />
			</Button>
			<DocsLink id="task-concurrency-guide" />
		</EmptyStateActions>
	</EmptyState>
);
