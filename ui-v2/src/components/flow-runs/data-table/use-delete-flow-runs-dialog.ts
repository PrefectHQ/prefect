import { useDeleteFlowRun } from "@/api/flow-runs";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { useToast } from "@/hooks/use-toast";

export const useDeleteFlowRunsDialog = () => {
	const { toast } = useToast();
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { mutateAsync } = useDeleteFlowRun();

	const handleDeletes = async (flowRunIds: Array<string>) => {
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
				toast({ title: `${numFails} flow runs failed to delete` });
			} else if (numFails === 1) {
				toast({ title: "Flow run failed to delete" });
			} else if (numSuccess > 1) {
				toast({ title: `${numSuccess} flow runs deleted` });
			} else {
				toast({ title: "Flow run deleted" });
			}
			// eslint-disable-next-line @typescript-eslint/no-unused-vars
		} catch (error) {
			console.error("Unknown error while deleting flow run.");
		}
	};

	const handleConfirmDelete = (flowRunIds: Array<string>) =>
		confirmDelete({
			title: "Delete Flow Runs",
			description: "Are you sure you want to delete selected flow runs?",
			onConfirm: () => {
				void handleDeletes(flowRunIds);
			},
		});

	return [dialogState, handleConfirmDelete] as const;
};
