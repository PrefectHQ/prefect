import { useDeleteDeploymentSchedule } from "@/api/deployments";
import type { DeploymentSchedule } from "@/api/deployments";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { useToast } from "@/hooks/use-toast";
import { getScheduleTitle } from "./get-schedule-title";

export const useDeleteSchedule = () => {
	const { toast } = useToast();
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { deleteDeploymentSchedule } = useDeleteDeploymentSchedule();

	const handleConfirmDelete = (deploymentSchedule: DeploymentSchedule) =>
		confirmDelete({
			title: "Delete Schedule",
			description: `Are you sure you want to delete ${getScheduleTitle(deploymentSchedule)} schedule?`,
			onConfirm: () => {
				const { id, deployment_id } = deploymentSchedule;
				if (!deployment_id) {
					throw new Error("'deployment_id' expected");
				}
				deleteDeploymentSchedule(
					{ deployment_id, schedule_id: id },
					{
						onSuccess: () => toast({ title: "Schedule deleted" }),
						onError: (error) => {
							const message =
								error.message || "Unknown error while deleting schedule.";
							console.error(message);
						},
					},
				);
			},
		});

	return [dialogState, handleConfirmDelete] as const;
};
