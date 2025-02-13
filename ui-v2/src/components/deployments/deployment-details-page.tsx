import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useMemo, useState } from "react";

import { DeploymentActionMenu } from "./deployment-action-menu";
import { DeploymentDetailsHeader } from "./deployment-details-header";
import { DeploymentDetailsTabs } from "./deployment-details-tabs";
import { DeploymentFlowLink } from "./deployment-flow-link";
import { DeploymentMetadata } from "./deployment-metadata";
import { DeploymentScheduleDialog } from "./deployment-schedules/deployment-schedule-dialog";
import { DeploymentSchedules } from "./deployment-schedules/deployment-schedules";
import { DeploymentTriggers } from "./deployment-triggers";
import { RunFlowButton } from "./run-flow-button";
import { useDeleteDeploymentConfirmationDialog } from "./use-delete-deployment-confirmation-dialog";

type Dialogs = "create" | "edit";

type DeploymentDetailsPageProps = {
	id: string;
};

export const DeploymentDetailsPage = ({ id }: DeploymentDetailsPageProps) => {
	const [showScheduleDialog, setShowScheduleDialog] = useState<Dialogs | null>(
		null,
	);
	const [scheduleIdToEdit, setScheduleIdToEdit] = useState("");

	const { data: deployment } = useSuspenseQuery(
		buildDeploymentDetailsQuery(id),
	);

	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteDeploymentConfirmationDialog();

	const scheduleToEdit = useMemo(() => {
		if (!deployment.schedules) {
			return undefined;
		}
		return deployment.schedules.find(
			(schedule) => schedule.id === scheduleIdToEdit,
		);
	}, [deployment.schedules, scheduleIdToEdit]);

	const handleAddSchedule = () => setShowScheduleDialog("create");
	const handleEditSchedule = (scheduleId: string) => {
		setScheduleIdToEdit(scheduleId);
		setShowScheduleDialog("edit");
	};
	const closeDialog = () => setShowScheduleDialog(null);
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
						<Suspense fallback={<LoadingSkeleton numSkeletons={1} />}>
							<DeploymentFlowLink flowId={deployment.flow_id} />
						</Suspense>
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
				<div className="grid gap-4" style={{ gridTemplateColumns: "3fr 1fr" }}>
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
				open={showScheduleDialog === "create"}
				onOpenChange={handleOpenChange}
			/>
			{scheduleToEdit && (
				<DeploymentScheduleDialog
					open={showScheduleDialog === "edit"}
					onOpenChange={handleOpenChange}
					scheduleToEdit={scheduleToEdit}
				/>
			)}
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
