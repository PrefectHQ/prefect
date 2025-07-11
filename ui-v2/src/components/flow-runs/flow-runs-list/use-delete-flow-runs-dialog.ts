import { toast } from "sonner";
import { useDeleteFlowRun } from "@/api/flow-runs";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

export const useDeleteFlowRunsDialog = () => {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { mutateAsync } = useDeleteFlowRun();

	const handleDeletes = async (
		flowRunIds: Array<string>,
		onConfirm = () => {},
	) => {
		try {
			const res = await Promise.allSettled(
				flowRunIds.map((id) => mutateAsync(id)),
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
				toast.error(`${numFails} flow runs failed to delete`);
			} else if (numFails === 1) {
				toast.error("Flow run failed to delete");
			} else if (numSuccess > 1) {
				toast.success(`${numSuccess} flow runs deleted`);
			} else {
				toast.success("Flow run deleted");
			}
		} catch (err) {
			console.error("Unknown error while deleting flow run.", err);
		} finally {
			onConfirm();
		}
	};

	const handleConfirmDelete = (
		flowRunIds: Array<string>,
		onConfirm = () => {},
	) =>
		confirmDelete({
			title: "Delete Flow Runs",
			description: "Are you sure you want to delete selected flow runs?",
			onConfirm: () => {
				void handleDeletes(flowRunIds, onConfirm);
			},
		});

	return [dialogState, handleConfirmDelete] as const;
};
