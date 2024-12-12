import { TaskRunConcurrencyLimitDeleteDialog } from "@/components/concurrency/_shared/task-run-concurrency-limit-delete-dialog";
import { TaskRunConcurrencyLimitResetDialog } from "@/components/concurrency/_shared/task-run-concurrency-limit-reset-dialog";
import { TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import { getRouteApi } from "@tanstack/react-router";

export type Dialogs = null | "delete" | "reset";

const routeApi = getRouteApi("/concurrency-limits/");

type Props = {
	data: TaskRunConcurrencyLimit;
	openDialog: Dialogs;
	onOpenChange: (open: boolean) => void;
	onCloseDialog: () => void;
};

export const DialogView = ({
	data,
	openDialog,
	onCloseDialog,
	onOpenChange,
}: Props) => {
	const navigate = routeApi.useNavigate();

	const handleDelete = () => {
		onCloseDialog();
		void navigate({ to: "/concurrency-limits", search: { tab: "task-run" } });
	};

	switch (openDialog) {
		case "reset":
			return (
				<TaskRunConcurrencyLimitResetDialog
					data={data}
					onOpenChange={onOpenChange}
					onReset={onCloseDialog}
				/>
			);
		case "delete":
			return (
				<TaskRunConcurrencyLimitDeleteDialog
					data={data}
					onOpenChange={onOpenChange}
					onDelete={handleDelete}
				/>
			);
		default:
			return null;
	}
};
