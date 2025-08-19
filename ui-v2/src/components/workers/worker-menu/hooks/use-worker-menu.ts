import { Copy, MoreHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { WorkPoolWorker } from "@/api/work-pools";

export const useWorkerMenu = (worker: WorkPoolWorker) => {
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);

	const handleCopyId = () => {
		void navigator.clipboard.writeText(worker.id);
		toast.success("ID copied to clipboard");
	};

	const menuItems = [
		{
			label: "Copy ID",
			icon: Copy,
			action: handleCopyId,
			show: true,
		},
		{
			label: "Delete",
			icon: Trash2,
			action: () => setShowDeleteDialog(true),
			show: true, // Workers can typically be deleted by work pool managers
			variant: "destructive" as const,
		},
	].filter((item) => item.show);

	return {
		menuItems,
		showDeleteDialog,
		setShowDeleteDialog,
		triggerIcon: MoreHorizontal,
	};
};
