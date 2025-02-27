import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useMemo, useState } from "react";

import { FlowLink } from "@/components/flows/flow-link";
import { WorkPoolLink } from "@/components/work-pools/work-pool-link";
import { WorkQueueLink } from "@/components/work-pools/work-queue-link";
import { DeploymentActionMenu } from "./deployment-action-menu";
import { DeploymentDetailsHeader } from "./deployment-details-header";
import { DeploymentDetailsTabs } from "./deployment-details-tabs";
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

	return (
		<>
			<div className="flex flex-col gap-4">
				<div className="flex align-middle justify-between">
					<div className="flex flex-col gap-2">
						<DeploymentDetailsHeader deployment={deployment} />
						<div className="flex items-center gap-4">
							<Suspense fallback={<LoadingSkeleton numSkeletons={1} />}>
								<FlowLink flowId={deployment.flow_id} />
							</Suspense>
							{deployment.work_pool_name && (
								<WorkPoolLink workPoolName={deployment.work_pool_name} />
							)}
							{deployment.work_pool_name && deployment.work_queue_name && (
								<WorkQueueLink
									workPoolName={deployment.work_pool_name}
									workQueueName={deployment.work_queue_name}
								/>
							)}
						</div>
					</div>
					<div className="flex align-middle gap-2">
						<RunFlowButton deployment={deployment} />
						<DeploymentActionMenu
							id={id}
							onDelete={() =>
								confirmDelete(deployment, { shouldNavigate: true })
							}
						/>
					</div>
				</div>
				<div className="grid gap-4" style={{ gridTemplateColumns: "5fr 1fr" }}>
					<div className="flex flex-col gap-5">
						<DeploymentDetailsTabs deployment={deployment} />
					</div>
					<div className="flex flex-col gap-3">
						<DeploymentSchedules
							deployment={deployment}
							onAddSchedule={handleAddSchedule}
							onEditSchedule={handleEditSchedule}
						/>

						<Suspense fallback={<LoadingSkeleton numSkeletons={2} />}>
							<DeploymentTriggers deployment={deployment} />
						</Suspense>

						<hr />
						<DeploymentMetadata deployment={deployment} />
					</div>
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

type LoadingSkeletonProps = {
	numSkeletons?: number;
};
const LoadingSkeleton = ({ numSkeletons = 1 }: LoadingSkeletonProps) => (
	<ul className="flex flex-col gap-1">
		{Array.from({ length: numSkeletons }).map((_, i) => (
			<li key={i}>
				<Skeleton className="h-4 w-full" />
			</li>
		))}
	</ul>
);
