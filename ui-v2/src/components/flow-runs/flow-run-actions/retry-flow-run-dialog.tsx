import { toast } from "sonner";
import { type FlowRun, useSetFlowRunState } from "@/api/flow-runs";
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
import { StateBadge } from "@/components/ui/state-badge";

type RetryFlowRunDialogProps = {
	flowRun: FlowRun;
	open: boolean;
	onOpenChange: (open: boolean) => void;
};

export const RetryFlowRunDialog = ({
	flowRun,
	open,
	onOpenChange,
}: RetryFlowRunDialogProps) => {
	const { setFlowRunState, isPending } = useSetFlowRunState();

	const handleRetry = () => {
		setFlowRunState(
			{
				id: flowRun.id,
				state: {
					type: "SCHEDULED",
					name: "AwaitingRetry",
					message: "Retry from the UI",
				},
				force: true,
			},
			{
				onSuccess: () => {
					toast.success("Flow run scheduled for retry");
					onOpenChange(false);
				},
				onError: (error) => {
					toast.error(error.message || "Failed to retry flow run");
				},
			},
		);
	};

	return (
		<AlertDialog open={open} onOpenChange={onOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Retry Flow Run</AlertDialogTitle>
					<AlertDialogDescription asChild>
						<div className="space-y-4">
							<p>
								Retry the flow run{" "}
								<span className="font-medium">{flowRun.name}</span>?
							</p>
							<div className="flex items-center gap-2">
								<span className="text-sm text-muted-foreground">
									Current state:
								</span>
								{flowRun.state_type && flowRun.state_name && (
									<StateBadge
										type={flowRun.state_type}
										name={flowRun.state_name}
									/>
								)}
							</div>
							<div className="flex items-center gap-2">
								<span className="text-sm text-muted-foreground">
									Will become:
								</span>
								<StateBadge type="SCHEDULED" name="AwaitingRetry" />
							</div>
							<p className="text-sm text-muted-foreground">
								Task runs with persisted results will use cached values. Task
								runs without persisted results will be re-executed.
							</p>
						</div>
					</AlertDialogDescription>
				</AlertDialogHeader>

				<AlertDialogFooter>
					<AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
					<AlertDialogAction
						onClick={(e) => {
							e.preventDefault();
							handleRetry();
						}}
						disabled={isPending}
					>
						{isPending ? "Retrying..." : "Retry"}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
};
