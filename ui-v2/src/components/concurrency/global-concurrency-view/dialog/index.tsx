import { GlobalConcurrencyLimit } from "@/hooks/global-concurrency-limits";

import { CreateOrEditLimitDialog } from "./create-or-edit-limit-dialog";
import { DeleteLimitDialog } from "./delete-limit-dialog";
import { ResetLimitDialog } from "./reset-limit-dialog";

export type DialogState =
	| { dialog: null | "create"; data: undefined }
	| {
			dialog: "reset" | "delete" | "edit";
			data: GlobalConcurrencyLimit;
	  };

export const DialogView = ({
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
				<CreateOrEditLimitDialog
					onOpenChange={onOpenChange}
					onSubmit={onCloseDialog}
				/>
			);
		case "reset":
			return (
				<ResetLimitDialog
					limit={data}
					onOpenChange={onOpenChange}
					onReset={onCloseDialog}
				/>
			);
		case "delete":
			return (
				<DeleteLimitDialog
					limit={data}
					onOpenChange={onOpenChange}
					onDelete={onCloseDialog}
				/>
			);
		case "edit":
			return (
				<CreateOrEditLimitDialog
					onOpenChange={onOpenChange}
					limitToUpdate={data}
					onSubmit={onCloseDialog}
				/>
			);
		default:
			return null;
	}
};
