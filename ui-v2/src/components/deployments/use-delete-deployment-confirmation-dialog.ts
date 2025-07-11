import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { type Deployment, useDeleteDeployment } from "@/api/deployments";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

export const useDeleteDeploymentConfirmationDialog = () => {
	const navigate = useNavigate();
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { deleteDeployment } = useDeleteDeployment();

	const handleConfirmDelete = (
		deployment: Deployment,
		{
			shouldNavigate = false,
		}: {
			/** Should navigate back to /deployments */
			shouldNavigate?: boolean;
		} = {},
	) =>
		confirmDelete({
			title: "Delete Deployment",
			description: `Are you sure you want to delete ${deployment.name}? This action cannot be undone.`,
			onConfirm: () => {
				deleteDeployment(deployment.id, {
					onSuccess: () => {
						toast.success("Deployment deleted");
						if (shouldNavigate) {
							void navigate({ to: "/deployments" });
						}
					},
					onError: (error) => {
						const message =
							error.message || "Unknown error while deleting deployment.";
						console.error(message);
					},
				});
			},
		});

	return [dialogState, handleConfirmDelete] as const;
};
