import type { CheckedState } from "@radix-ui/react-checkbox";
import { useMemo } from "react";
import type { TaskRunResponse } from "@/api/task-runs";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";
import { useDeleteTaskRunsDialog } from "./use-delete-task-runs-dialog";

type CountOnlyProps = {
	count: number | undefined;
};
type SelectableProps = {
	count: number | undefined;
	results: Array<TaskRunResponse> | undefined;
	setSelectedRows: (rows: Set<string>) => void;
	selectedRows: Set<string>;
};
type TaskRunsRowCountProps = CountOnlyProps | SelectableProps;

export const TaskRunsRowCount = ({
	count = 0,
	...props
}: TaskRunsRowCountProps) => {
	// Selectable UX
	if (
		"results" in props &&
		"setSelectedRows" in props &&
		"selectedRows" in props
	) {
		return <SelectedCount count={count} {...props} />;
	}

	// Count only UX
	return (
		<Typography variant="bodySmall" className="text-muted-foreground">
			{count} {pluralize(count, "Task run")}
		</Typography>
	);
};

function SelectedCount({
	count = 0,
	results = [],
	setSelectedRows,
	selectedRows,
}: SelectableProps) {
	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteTaskRunsDialog();

	const resultsIds = useMemo(() => results.map(({ id }) => id), [results]);

	const selectedRowsList = Array.from(selectedRows);

	const ToggleCheckbox = () => {
		const isAllRowsSelected = resultsIds.every((id) => selectedRows.has(id));
		const isSomeRowsSelected = resultsIds.some((id) => selectedRows.has(id));
		let checkedState: CheckedState = false;
		if (isAllRowsSelected) {
			checkedState = true;
		} else if (isSomeRowsSelected) {
			checkedState = "indeterminate";
		}
		return (
			<Checkbox
				className="block"
				checked={checkedState}
				onCheckedChange={(checked) => {
					if (checked) {
						setSelectedRows(new Set(resultsIds));
					} else {
						setSelectedRows(new Set());
					}
				}}
				aria-label="Toggle all"
			/>
		);
	};

	// If has selected rows
	if (selectedRows.size > 0)
		return (
			<>
				<div className="flex items-center gap-2">
					<ToggleCheckbox />
					<Typography variant="bodySmall" className="text-muted-foreground">
						{selectedRowsList.length} selected
					</Typography>
					<Button
						aria-label="Delete rows"
						size="icon"
						variant="secondary"
						onClick={() => {
							confirmDelete(selectedRowsList, () => setSelectedRows(new Set()));
						}}
					>
						<Icon id="Trash2" className="size-4" />
					</Button>
				</div>
				<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
			</>
		);

	return (
		<div className="flex items-center gap-2">
			{results && setSelectedRows && selectedRows && (
				<Checkbox
					className="block"
					checked={false}
					onCheckedChange={(checked) => {
						setSelectedRows(new Set(checked ? resultsIds : undefined));
					}}
					aria-label="Toggle all"
				/>
			)}
			<Typography variant="bodySmall" className="text-muted-foreground">
				{count} {pluralize(count, "Task run")}
			</Typography>
		</div>
	);
}
