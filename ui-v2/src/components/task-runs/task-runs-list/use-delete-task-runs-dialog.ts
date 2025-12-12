import { toast } from "sonner";
import { useDeleteTaskRun } from "@/api/task-runs";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

export const useDeleteTaskRunsDialog = () => {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { mutateAsync } = useDeleteTaskRun();

	const handleDeletes = async (
		taskRunIds: Array<string>,
		onConfirm = () => {},
	) => {
		try {
			const res = await Promise.allSettled(
				taskRunIds.map((id) => mutateAsync({ id })),
			);
			const { numFails, numSuccess } = res.reduce(
				(accumulator, currentValue) => {
					if (currentValue.status === "rejected") {
						accumulator.numFails += 1;
					} else {
						accumulator.numSuccess += 1;
					}
					return accumulator;
				},
				{ numFails: 0, numSuccess: 0 },
			);
			if (numFails > 1) {
				toast.error(`${numFails} task runs failed to delete`);
			} else if (numFails === 1) {
				toast.error("Task run failed to delete");
			} else if (numSuccess > 1) {
				toast.success(`${numSuccess} task runs deleted`);
			} else {
				toast.success("Task run deleted");
			}
		} catch (err) {
			console.error("Unknown error while deleting task run.", err);
		} finally {
			onConfirm();
		}
	};

	const handleConfirmDelete = (
		taskRunIds: Array<string>,
		onConfirm = () => {},
	) =>
		confirmDelete({
			title: "Delete Task Runs",
			description: "Are you sure you want to delete selected task runs?",
			onConfirm: () => {
				void handleDeletes(taskRunIds, onConfirm);
			},
		});

	return [dialogState, handleConfirmDelete] as const;
};
