import { useNavigate } from "@tanstack/react-router";
import { Copy, Edit, MoreVertical, Trash2, Zap } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { WorkPoolQueue } from "@/api/work-pool-queues";

export const useWorkPoolQueueMenu = (queue: WorkPoolQueue) => {
	const navigate = useNavigate();
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const [showEditDialog, setShowEditDialog] = useState(false);

	const handleCopyId = () => {
		void navigator.clipboard.writeText(queue.id);
		toast.success("ID copied to clipboard");
	};

	const handleEdit = () => {
		setShowEditDialog(true);
	};

	const handleAutomate = () => {
		void navigate({
			to: "/automations/create",
		});
	};

	const isDefaultQueue = queue.name === "default";

	const menuItems = [
		{
			label: "Copy ID",
			icon: Copy,
			action: handleCopyId,
			show: true,
		},
		{
			label: "Edit",
			icon: Edit,
			action: handleEdit,
			show: true,
		},
		{
			label: "Delete",
			icon: Trash2,
			action: () => setShowDeleteDialog(true),
			show: !isDefaultQueue, // Default queue cannot be deleted
			variant: "destructive" as const,
		},
		{
			label: "Automate",
			icon: Zap,
			action: handleAutomate,
			show: true,
		},
	].filter((item) => item.show);

	return {
		menuItems,
		showDeleteDialog,
		setShowDeleteDialog,
		showEditDialog,
		setShowEditDialog,
		triggerIcon: MoreVertical,
	};
};
