import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import type { WorkPool } from "@/api/work-pools";
import { useDeleteWorkPool } from "@/api/work-pools";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface DeleteWorkPoolDialogProps {
	workPool: WorkPool;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onDeleted?: () => void;
}

export const DeleteWorkPoolDialog = ({
	workPool,
	open,
	onOpenChange,
	onDeleted,
}: DeleteWorkPoolDialogProps) => {
	const navigate = useNavigate();
	const [confirmName, setConfirmName] = useState("");
	const { deleteWorkPool, isPending } = useDeleteWorkPool();

	const handleDelete = () => {
		if (confirmName !== workPool.name) {
			toast.error("Work pool name does not match");
			return;
		}

		deleteWorkPool(workPool.name, {
			onSuccess: () => {
				toast.success("Work pool deleted successfully");
				onOpenChange(false);
				onDeleted?.();
				void navigate({ to: "/work-pools" });
			},
			onError: () => {
				toast.error("Failed to delete work pool");
			},
		});
	};

	const handleOpenChange = (newOpen: boolean) => {
		if (!newOpen) {
			setConfirmName("");
		}
		onOpenChange(newOpen);
	};

	return (
		<AlertDialog open={open} onOpenChange={handleOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Delete Work Pool</AlertDialogTitle>
					<AlertDialogDescription>
						Are you sure you want to delete the work pool &ldquo;{workPool.name}
						&rdquo;? This action cannot be undone.
					</AlertDialogDescription>
				</AlertDialogHeader>
				<div className="space-y-2">
					<Label htmlFor="confirm-name">
						Type <strong>{workPool.name}</strong> to confirm:
					</Label>
					<Input
						id="confirm-name"
						value={confirmName}
						onChange={(e) => setConfirmName(e.target.value)}
						placeholder={workPool.name}
					/>
				</div>
				<AlertDialogFooter>
					<AlertDialogCancel>Cancel</AlertDialogCancel>
					<AlertDialogAction
						onClick={handleDelete}
						disabled={confirmName !== workPool.name || isPending}
						className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
					>
						{isPending ? "Deleting..." : "Delete"}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
};
