import { Deployment, useDeleteDeployment } from "@/api/deployments";
import { useDeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { useToast } from "@/hooks/use-toast";
import { getRouteApi } from "@tanstack/react-router";

const routeApi = getRouteApi("/deployments/");

export const useDeleteDeploymentConfirmationDialog = () => {
	const navigate = routeApi.useNavigate();
	const { toast } = useToast();
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
						toast({ title: "Deployment deleted" });
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
