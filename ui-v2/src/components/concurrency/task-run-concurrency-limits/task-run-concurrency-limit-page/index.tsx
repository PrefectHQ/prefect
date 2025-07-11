import { useSuspenseQuery } from "@tanstack/react-query";
import { Await } from "@tanstack/react-router";
import { useState } from "react";
import { buildConcurrenyLimitDetailsActiveRunsQuery } from "@/api/task-run-concurrency-limits";
import { TaskRunConcurrencyLimitActiveTaskRuns } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limit-active-task-runs";
import { TaskRunConcurrencyLimitDetails } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limit-details";
import { TaskRunConcurrencyLimitHeader } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limit-header";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
	type Dialogs,
	TaskRunConcurrencyLimitDialog,
} from "./task-run-concurrency-limit-dialog";
import { TaskRunConcurrencyLimitTabNavigation } from "./task-run-concurrency-limit-tab-navigation";

type TaskRunConcurrencyLimitPageProps = {
	id: string;
};

export const TaskRunConcurrencyLimitPage = ({
	id,
}: TaskRunConcurrencyLimitPageProps) => {
	const [openDialog, setOpenDialog] = useState<Dialogs>(null);
	const { data } = useSuspenseQuery(
		buildConcurrenyLimitDetailsActiveRunsQuery(id),
	);

	const handleOpenDeleteDialog = () => setOpenDialog("delete");
	const handleOpenResetDialog = () => setOpenDialog("reset");
	const handleCloseDialog = () => setOpenDialog(null);

	// Because all modals will be rendered, only control the closing logic
	const handleOpenChange = (open: boolean) => {
		if (!open) {
			handleCloseDialog();
		}
	};

	const { activeTaskRunsPromise, taskRunConcurrencyLimit } = data;
	const numActiveTaskRuns = taskRunConcurrencyLimit.active_slots?.length;
	return (
		<>
			<div className="flex flex-col gap-4">
				<TaskRunConcurrencyLimitHeader
					data={taskRunConcurrencyLimit}
					onDelete={handleOpenDeleteDialog}
					onReset={handleOpenResetDialog}
				/>
				<div className="grid gap-4" style={{ gridTemplateColumns: "3fr 1fr" }}>
					<TaskRunConcurrencyLimitTabNavigation>
						<Await
							promise={activeTaskRunsPromise}
							fallback={<SkeletonLoading length={numActiveTaskRuns} />}
						>
							{(activeTaskRuns) => (
								<TaskRunConcurrencyLimitActiveTaskRuns data={activeTaskRuns} />
							)}
						</Await>
					</TaskRunConcurrencyLimitTabNavigation>
					<TaskRunConcurrencyLimitDetails data={taskRunConcurrencyLimit} />
				</div>
			</div>
			<TaskRunConcurrencyLimitDialog
				data={taskRunConcurrencyLimit}
				openDialog={openDialog}
				onOpenChange={handleOpenChange}
				onCloseDialog={handleCloseDialog}
			/>
		</>
	);
};

type SkeletonLoadingProps = { length?: number };
const SkeletonLoading = ({ length = 0 }: SkeletonLoadingProps) => (
	<div className="flex flex-col gap-4">
		{Array.from({ length }, (_, index) => (
			// biome-ignore lint/suspicious/noArrayIndexKey: okay for static skeleton list
			<Card key={index} className="p-4 space-y-4">
				<Skeleton className="h-4 w-[350px]" />
				<Skeleton className="h-4 w-[400px]" />
			</Card>
		))}
	</div>
);
