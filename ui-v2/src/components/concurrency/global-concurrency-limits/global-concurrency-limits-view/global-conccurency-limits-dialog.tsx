import type { GlobalConcurrencyLimit } from "@/api/global-concurrency-limits";

import { GlobalConcurrencyLimitsCreateOrEditDialog } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-create-or-edit-dialog";
import { GlobalConcurrencyLimitsDeleteDialog } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-delete-dialog";

export type DialogState =
	| { dialog: null | "create"; data: undefined }
	| {
			dialog: "delete" | "edit";
			data: GlobalConcurrencyLimit;
	  };

export const GlobalConcurrencyLimitsDialog = ({
	openDialog,
	onCloseDialog,
	onOpenChange,
}: {
	openDialog: DialogState;
	onOpenChange: (open: boolean) => void;
	onCloseDialog: () => void;
}) => {
	const { dialog, data } = openDialog;
	switch (dialog) {
		case "create":
			return (
				<GlobalConcurrencyLimitsCreateOrEditDialog
					onOpenChange={onOpenChange}
					onSubmit={onCloseDialog}
				/>
			);
		case "delete":
			return (
				<GlobalConcurrencyLimitsDeleteDialog
					limit={data}
					onOpenChange={onOpenChange}
					onDelete={onCloseDialog}
				/>
			);
		case "edit":
			return (
				<GlobalConcurrencyLimitsCreateOrEditDialog
					onOpenChange={onOpenChange}
					limitToUpdate={data}
					onSubmit={onCloseDialog}
				/>
			);
		default:
			return null;
	}
};
