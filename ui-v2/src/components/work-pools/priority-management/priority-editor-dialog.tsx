import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useBulkUpdatePrioritiesMutation } from "./use-bulk-update-priorities-mutation";

type PriorityEditorDialogProps = {
	queues: WorkPoolQueue[];
	workPoolName: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onUpdated?: () => void;
};

export const PriorityEditorDialog = ({
	queues,
	workPoolName,
	open,
	onOpenChange,
	onUpdated,
}: PriorityEditorDialogProps) => {
	// Initialize priorities from queues when dialog opens
	const getInitialPriorities = useCallback(() => {
		return queues.reduce(
			(acc, queue) => {
				acc[queue.id] = queue.priority ?? 1;
				return acc;
			},
			{} as Record<string, number>,
		);
	}, [queues]);

	const [priorities, setPriorities] =
		useState<Record<string, number>>(getInitialPriorities);
	const updatePrioritiesMutation = useBulkUpdatePrioritiesMutation();

	// Reset priorities when dialog opens
	useEffect(() => {
		if (open) {
			const initialPriorities = getInitialPriorities();
			queueMicrotask(() => setPriorities(initialPriorities));
		}
	}, [open, getInitialPriorities]);

	const handleSave = () => {
		const updates = queues.map((queue) => ({
			id: queue.id,
			priority: priorities[queue.id] ?? queue.priority ?? 1,
		}));

		updatePrioritiesMutation.mutate(
			{ workPoolName, updates },
			{
				onSuccess: () => {
					onUpdated?.();
					onOpenChange(false);
					toast.success("Priorities updated successfully");
				},
				onError: (error) => {
					console.error("Failed to update priorities:", error);
					toast.error("Failed to update priorities");
				},
			},
		);
	};

	const handleOpenChange = (newOpen: boolean) => {
		if (!newOpen) {
			// Reset priorities when closing
			const initialPriorities = queues.reduce(
				(acc, queue) => {
					acc[queue.id] = queue.priority ?? 1;
					return acc;
				},
				{} as Record<string, number>,
			);
			setPriorities(initialPriorities);
		}
		onOpenChange(newOpen);
	};

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="max-w-md">
				<DialogHeader>
					<DialogTitle>Edit Queue Priorities</DialogTitle>
					<DialogDescription>
						Lower numbers have higher priority. Changes will affect work
						distribution.
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-4">
					{queues.map((queue) => (
						<div key={queue.id} className="flex items-center justify-between">
							<Label className="flex-1">{queue.name}</Label>
							<Input
								type="number"
								value={priorities[queue.id] ?? queue.priority ?? 1}
								onChange={(e) =>
									setPriorities((prev) => ({
										...prev,
										[queue.id]: Number.parseInt(e.target.value) || 0,
									}))
								}
								className="w-20"
								min="0"
							/>
						</div>
					))}
				</div>

				<DialogFooter>
					<Button variant="outline" onClick={() => onOpenChange(false)}>
						Cancel
					</Button>
					<Button
						onClick={handleSave}
						disabled={updatePrioritiesMutation.isPending}
					>
						{updatePrioritiesMutation.isPending ? "Saving..." : "Save Changes"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};
