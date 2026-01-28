import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import {
	buildFilterFlowRunsQuery,
	type FlowRun,
	useSetFlowRunState,
} from "@/api/flow-runs";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { StateBadge } from "@/components/ui/state-badge";

type CancelFlowRunDialogProps = {
	flowRun: FlowRun;
	open: boolean;
	onOpenChange: (open: boolean) => void;
};

export const CancelFlowRunDialog = ({
	flowRun,
	open,
	onOpenChange,
}: CancelFlowRunDialogProps) => {
	const [cancelSubFlows, setCancelSubFlows] = useState(false);
	const { setFlowRunState, isPending } = useSetFlowRunState();

	const { data: subFlowRuns = [] } = useQuery({
		...buildFilterFlowRunsQuery({
			flow_runs: {
				parent_flow_run_id: { any_: [flowRun.id] },
				state: {
					type: { any_: ["RUNNING", "SCHEDULED", "PENDING", "PAUSED"] },
				},
			},
			limit: 100,
			offset: 0,
		}),
		enabled: open,
	});

	const hasSubFlows = subFlowRuns.length > 0;

	const cancelSubFlowRuns = (errors: string[]) => {
		for (const subFlow of subFlowRuns) {
			setFlowRunState(
				{
					id: subFlow.id,
					state: { type: "CANCELLING", name: "Cancelling" },
					force: true,
				},
				{
					onError: () => {
						errors.push(subFlow.name ?? subFlow.id);
					},
				},
			);
		}
	};

	const handleCancel = () => {
		setFlowRunState(
			{
				id: flowRun.id,
				state: {
					type: "CANCELLING",
					name: "Cancelling",
				},
				force: true,
			},
			{
				onSuccess: () => {
					if (cancelSubFlows && subFlowRuns.length > 0) {
						const errors: string[] = [];
						cancelSubFlowRuns(errors);
						if (errors.length > 0) {
							toast.error(
								`Failed to cancel some sub-flows: ${errors.join(", ")}`,
							);
						} else {
							toast.success(
								`Flow run and ${subFlowRuns.length} sub-flow${subFlowRuns.length === 1 ? "" : "s"} cancelled`,
							);
						}
					} else {
						toast.success("Flow run cancelled");
					}
					onOpenChange(false);
				},
				onError: (error) => {
					toast.error(error.message || "Failed to cancel flow run");
				},
			},
		);
	};

	return (
		<AlertDialog open={open} onOpenChange={onOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Cancel Flow Run</AlertDialogTitle>
					<AlertDialogDescription asChild>
						<div className="space-y-4">
							<p>
								Are you sure you want to cancel{" "}
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
								<StateBadge type="CANCELLING" name="Cancelling" />
							</div>
						</div>
					</AlertDialogDescription>
				</AlertDialogHeader>

				{hasSubFlows && (
					<div className="flex items-center space-x-2 py-2">
						<Checkbox
							id="cancel-subflows"
							checked={cancelSubFlows}
							onCheckedChange={(checked) => setCancelSubFlows(checked === true)}
						/>
						<Label htmlFor="cancel-subflows" className="text-sm cursor-pointer">
							Also cancel {subFlowRuns.length} sub-flow run
							{subFlowRuns.length === 1 ? "" : "s"}
						</Label>
					</div>
				)}

				<AlertDialogFooter>
					<AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
					<AlertDialogAction
						onClick={(e) => {
							e.preventDefault();
							void handleCancel();
						}}
						disabled={isPending}
					>
						{isPending ? "Cancelling..." : "Cancel Flow Run"}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
};
