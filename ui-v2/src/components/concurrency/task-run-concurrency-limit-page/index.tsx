import { TaskRunConcurrencyLimitHeader } from "@/components/concurrency/task-run-concurrency-limit-header";
import { useGetTaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import { useState } from "react";

import { TaskRunConcurrencyLimitActiveTaskRuns } from "@/components/concurrency/task-run-concurrency-limit-active-task-runs";
import { TaskRunConcurrencyLimitDetails } from "@/components/concurrency/task-run-concurrency-limit-details";
import {
	type Dialogs,
	TaskRunConcurrencyLimitDialog,
} from "./task-run-concurrency-limit-dialog";
import { TaskRunConcurrencyLimitTabNavigation } from "./task-run-concurrency-limit-tab-navigation";

type Props = {
	id: string;
};

export const TaskRunConcurrencyLimitPage = ({ id }: Props) => {
	const [openDialog, setOpenDialog] = useState<Dialogs>(null);
	const { data } = useGetTaskRunConcurrencyLimit(id);

	const handleOpenDeleteDialog = () => setOpenDialog("delete");
	const handleOpenResetDialog = () => setOpenDialog("reset");
	const handleCloseDialog = () => setOpenDialog(null);

	// Because all modals will be rendered, only control the closing logic
	const handleOpenChange = (open: boolean) => {
		if (!open) {
			handleCloseDialog();
		}
	};

	return (
		<>
			<div className="flex flex-col gap-4">
				<TaskRunConcurrencyLimitHeader
					data={data}
					onDelete={handleOpenDeleteDialog}
					onReset={handleOpenResetDialog}
				/>
				<div className="grid gap-4" style={{ gridTemplateColumns: "3fr 1fr" }}>
					<TaskRunConcurrencyLimitTabNavigation
						activetaskRunsView={<TaskRunConcurrencyLimitActiveTaskRuns />}
					/>
					<TaskRunConcurrencyLimitDetails data={data} />
				</div>
			</div>
			<TaskRunConcurrencyLimitDialog
				data={data}
				openDialog={openDialog}
				onOpenChange={handleOpenChange}
				onCloseDialog={handleCloseDialog}
			/>
		</>
	);
};
