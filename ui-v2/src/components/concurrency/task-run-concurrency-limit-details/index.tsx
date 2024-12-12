import { useGetTaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import { useState } from "react";

import { ActiveTaskRunsView } from "./active-task-runs-view";
import { DialogView, type Dialogs } from "./dialogs";
import { Header } from "./header";
import { SideDetails } from "./side-details";
import { TabNavigation } from "./tab-navigation";

type Props = {
	id: string;
};

export const TaskRunConcurrencyLimitDetailsPage = ({ id }: Props) => {
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
				<Header
					data={data}
					onDelete={handleOpenDeleteDialog}
					onReset={handleOpenResetDialog}
				/>
				<div className="grid gap-4" style={{ gridTemplateColumns: "3fr 1fr" }}>
					<TabNavigation activetaskRunsView={<ActiveTaskRunsView />} />
					<SideDetails data={data} />
				</div>
			</div>
			<DialogView
				data={data}
				openDialog={openDialog}
				onOpenChange={handleOpenChange}
				onCloseDialog={handleCloseDialog}
			/>
		</>
	);
};
