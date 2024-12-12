import { type TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import { Link } from "@tanstack/react-router";
import { CellContext } from "@tanstack/react-table";

type Props = CellContext<TaskRunConcurrencyLimit, string>;

export const TagCell = (props: Props) => {
	const tag = props.getValue();
	const id = props.row.original.id;
	if (!id) {
		throw new Error("Expecting 'id' field");
	}
	return (
		<Link params={{ id }} to={"/concurrency-limits/concurrency-limit/$id"}>
			{tag}
		</Link>
	);
};
