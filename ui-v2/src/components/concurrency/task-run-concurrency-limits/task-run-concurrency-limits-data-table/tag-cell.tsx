import { Link } from "@tanstack/react-router";
import type { CellContext } from "@tanstack/react-table";
import type { TaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";

type TagCellProps = CellContext<TaskRunConcurrencyLimit, string>;

export const TagCell = (props: TagCellProps) => {
	const tag = props.getValue();
	const id = props.row.original.id;
	return (
		<Link
			params={{ id }}
			to={"/concurrency-limits/concurrency-limit/$id"}
			className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium bg-secondary text-secondary-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
		>
			{tag}
		</Link>
	);
};
