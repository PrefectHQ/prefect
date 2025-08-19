import { CheckCircle, Trash2 } from "lucide-react";
import { useState } from "react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BulkDeleteQueuesDialog } from "./bulk-delete-queues-dialog";

type BulkOperationsToolbarProps = {
	selectedQueues: WorkPoolQueue[];
	onClearSelection: () => void;
	workPoolName: string;
	className?: string;
};

export const BulkOperationsToolbar = ({
	selectedQueues,
	onClearSelection,
	workPoolName,
	className,
}: BulkOperationsToolbarProps) => {
	const [showBulkDeleteDialog, setShowBulkDeleteDialog] = useState(false);

	const canDelete = selectedQueues.some(
		(queue) => queue.name !== "default", // Can't delete default queue
	);

	const deletableQueues = selectedQueues.filter(
		(queue) => queue.name !== "default",
	);

	return (
		<div
			className={cn(
				"flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg",
				className,
			)}
		>
			<div className="flex items-center space-x-2">
				<CheckCircle className="h-4 w-4 text-blue-600" />
				<span className="text-sm font-medium text-blue-900">
					{selectedQueues.length} queue{selectedQueues.length === 1 ? "" : "s"}{" "}
					selected
				</span>
			</div>

			<div className="flex items-center space-x-2">
				<Button variant="ghost" size="sm" onClick={onClearSelection}>
					Clear selection
				</Button>

				{canDelete && deletableQueues.length > 0 && (
					<Button
						variant="destructive"
						size="sm"
						onClick={() => setShowBulkDeleteDialog(true)}
					>
						<Trash2 className="h-4 w-4 mr-2" />
						Delete ({deletableQueues.length})
					</Button>
				)}
			</div>

			<BulkDeleteQueuesDialog
				queues={deletableQueues}
				workPoolName={workPoolName}
				open={showBulkDeleteDialog}
				onOpenChange={setShowBulkDeleteDialog}
				onDeleted={() => {
					onClearSelection();
				}}
			/>
		</div>
	);
};
