import { useNavigate } from "@tanstack/react-router";
import { Copy, Edit, MoreVertical, Trash2, Zap } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { WorkPool } from "@/api/work-pools";

export const useWorkPoolMenu = (workPool: WorkPool) => {
	const navigate = useNavigate();
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);

	const handleCopyId = () => {
		void navigator.clipboard.writeText(workPool.id);
		toast.success("ID copied to clipboard");
	};

	const handleEdit = () => {
		void navigate({
			to: "/work-pools/work-pool/$workPoolName/edit",
			params: { workPoolName: workPool.name },
		});
	};

	const handleAutomate = () => {
		// TODO: Add search params when route supports it
		void navigate({
			to: "/automations/create",
		});
	};

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
			show: true, // TODO: Check workPool.can?.update when permissions are available
		},
		{
			label: "Delete",
			icon: Trash2,
			action: () => setShowDeleteDialog(true),
			show: true, // TODO: Check workPool.can?.delete when permissions are available
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
		triggerIcon: MoreVertical,
	};
};
