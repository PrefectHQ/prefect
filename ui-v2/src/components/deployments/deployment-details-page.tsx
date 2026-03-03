import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { LayoutWellSidebar } from "@/components/ui/layout-well";

import { DeploymentActionMenu } from "./deployment-action-menu";
import { DeploymentDetailsHeader } from "./deployment-details-header";
import { DeploymentDetailsTabs } from "./deployment-details-tabs";
import { DeploymentLinks } from "./deployment-links";
import { DeploymentMetadata } from "./deployment-metadata";
import { DeploymentScheduleDialog } from "./deployment-schedules/deployment-schedule-dialog";
import { DeploymentSchedules } from "./deployment-schedules/deployment-schedules";
import { DeploymentTriggers } from "./deployment-triggers";
import { RunFlowButton } from "./run-flow-button";
import { useDeleteDeploymentConfirmationDialog } from "./use-delete-deployment-confirmation-dialog";

type DeploymentDetailsPageProps = {
	id: string;
};

export const DeploymentDetailsPage = ({ id }: DeploymentDetailsPageProps) => {
	const [showScheduleDialog, setShowScheduleDialog] = useState({
		open: false,
		scheduleIdToEdit: "",
	});

	const { data: deployment } = useSuspenseQuery(
		buildDeploymentDetailsQuery(id),
	);

	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteDeploymentConfirmationDialog();

	const scheduleToEdit = useMemo(() => {
		if (!deployment.schedules || !showScheduleDialog.scheduleIdToEdit) {
			return undefined;
		}
		return deployment.schedules.find(
			(schedule) => schedule.id === showScheduleDialog.scheduleIdToEdit,
		);
	}, [deployment.schedules, showScheduleDialog.scheduleIdToEdit]);

	const handleAddSchedule = () =>
		setShowScheduleDialog({ open: true, scheduleIdToEdit: "" });
	const handleEditSchedule = (scheduleId: string) =>
		setShowScheduleDialog({ open: true, scheduleIdToEdit: scheduleId });
	const closeDialog = () =>
		setShowScheduleDialog({ open: false, scheduleIdToEdit: "" });
	const handleOpenChange = (open: boolean) => {
		// nb: Only need to handle when closing the dialog
		if (!open) {
			closeDialog();
		}
	};

	const sidebarContent = (
		<div className="flex flex-col gap-4">
			<DeploymentSchedules
				deployment={deployment}
				onAddSchedule={handleAddSchedule}
				onEditSchedule={handleEditSchedule}
			/>
			<DeploymentTriggers deployment={deployment} />
			<hr />
			<DeploymentMetadata deployment={deployment} />
		</div>
	);

	return (
		<>
			<div className="flex flex-col gap-4">
				<div className="flex items-center justify-between">
					<div className="flex flex-col gap-2">
						<DeploymentDetailsHeader deployment={deployment} />
						<DeploymentLinks deployment={deployment} />
					</div>
					<div className="flex items-center gap-2">
						<RunFlowButton deployment={deployment} />
						<DeploymentActionMenu
							id={id}
							onDelete={() =>
								confirmDelete(deployment, { shouldNavigate: true })
							}
						/>
					</div>
				</div>
				<div className="flex flex-col lg:flex-row lg:gap-6">
					<div className="flex-1 min-w-0">
						<DeploymentDetailsTabs
							deployment={deployment}
							detailsContent={sidebarContent}
						/>
					</div>
					<LayoutWellSidebar>{sidebarContent}</LayoutWellSidebar>
				</div>
			</div>
			<DeploymentScheduleDialog
				deploymentId={id}
				open={showScheduleDialog.open}
				onOpenChange={handleOpenChange}
				scheduleToEdit={scheduleToEdit}
				onSubmit={closeDialog}
			/>

			<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
		</>
	);
};
