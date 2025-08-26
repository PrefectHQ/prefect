import { useState } from "react";
import { toast } from "sonner";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
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
import { useBulkDeleteWorkPoolQueuesMutation } from "./use-bulk-delete-work-pool-queues-mutation";

type BulkDeleteQueuesDialogProps = {
	queues: WorkPoolQueue[];
	workPoolName: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onDeleted?: () => void;
};

export const BulkDeleteQueuesDialog = ({
	queues,
	workPoolName,
	open,
	onOpenChange,
	onDeleted,
}: BulkDeleteQueuesDialogProps) => {
	const [confirmationText, setConfirmationText] = useState("");
	const deleteQueuesMutation = useBulkDeleteWorkPoolQueuesMutation();

	const expectedConfirmation = `delete ${queues.length} queues`;
	const canConfirm = confirmationText === expectedConfirmation;

	const handleDelete = () => {
		if (!canConfirm) return;

		deleteQueuesMutation.mutate(
			{
				workPoolName,
				queueNames: queues.map((q) => q.name),
			},
			{
				onSuccess: () => {
					onDeleted?.();
					onOpenChange(false);
					setConfirmationText("");
					toast.success(`Deleted ${queues.length} queue(s) successfully`);
				},
				onError: (error) => {
					console.error("Failed to delete queues:", error);
					toast.error("Failed to delete queues");
				},
			},
		);
	};

	const handleOpenChange = (newOpen: boolean) => {
		if (!newOpen) {
			setConfirmationText("");
		}
		onOpenChange(newOpen);
	};

	return (
		<AlertDialog open={open} onOpenChange={handleOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Delete {queues.length} Queues</AlertDialogTitle>
					<AlertDialogDescription>
						This action cannot be undone. This will permanently delete the
						following queues:
						<ul className="mt-2 space-y-1">
							{queues.map((queue) => (
								<li key={queue.id} className="font-mono text-sm">
									• {queue.name}
								</li>
							))}
						</ul>
					</AlertDialogDescription>
				</AlertDialogHeader>

				<div className="space-y-4">
					<div>
						<Label htmlFor="confirmation">
							Type{" "}
							<span className="font-mono font-semibold">
								{expectedConfirmation}
							</span>{" "}
							to confirm:
						</Label>
						<Input
							id="confirmation"
							value={confirmationText}
							onChange={(e) => setConfirmationText(e.target.value)}
							placeholder={expectedConfirmation}
							className="mt-1"
						/>
					</div>
				</div>

				<AlertDialogFooter>
					<AlertDialogCancel>Cancel</AlertDialogCancel>
					<AlertDialogAction
						onClick={handleDelete}
						disabled={!canConfirm || deleteQueuesMutation.isPending}
						className="bg-red-600 hover:bg-red-700"
					>
						{deleteQueuesMutation.isPending ? "Deleting..." : "Delete Queues"}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
};
