import { useState } from "react";
import { toast } from "sonner";
import { type FlowRun, useSetFlowRunState } from "@/api/flow-runs";
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
import { StateBadge } from "@/components/ui/state-badge";
import { secondsToApproximateString } from "@/utils";

type PauseFlowRunDialogProps = {
	flowRun: FlowRun;
	open: boolean;
	onOpenChange: (open: boolean) => void;
};

export const PauseFlowRunDialog = ({
	flowRun,
	open,
	onOpenChange,
}: PauseFlowRunDialogProps) => {
	const [timeout, setTimeout] = useState(300); // 5 minutes default
	const { setFlowRunState, isPending } = useSetFlowRunState();

	const handlePause = () => {
		const pauseTimeout = new Date(Date.now() + timeout * 1000).toISOString();

		setFlowRunState(
			{
				id: flowRun.id,
				state: {
					type: "PAUSED",
					name: "Suspended",
					state_details: {
						pause_timeout: pauseTimeout,
						pause_reschedule: true,
					},
				},
				force: true,
			},
			{
				onSuccess: () => {
					toast.success("Flow run paused");
					onOpenChange(false);
				},
				onError: (error) => {
					toast.error(error.message || "Failed to pause flow run");
				},
			},
		);
	};

	const isValidTimeout = timeout >= 5;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Pause Flow Run</DialogTitle>
					<DialogDescription asChild>
						<div className="space-y-4">
							<p>
								Pause <span className="font-medium">{flowRun.name}</span> for a
								specified duration. The flow will automatically resume after the
								timeout.
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
								<StateBadge type="PAUSED" name="Suspended" />
							</div>
						</div>
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-2 py-4">
					<Label htmlFor="timeout">Timeout (seconds)</Label>
					<Input
						id="timeout"
						type="number"
						min={5}
						value={timeout}
						onChange={(e) =>
							setTimeout(Number.parseInt(e.target.value, 10) || 5)
						}
					/>
					<p className="text-sm text-muted-foreground">
						Will pause for {secondsToApproximateString(timeout)}. Minimum 5
						seconds.
					</p>
				</div>

				<DialogFooter>
					<Button
						type="button"
						variant="outline"
						onClick={() => onOpenChange(false)}
						disabled={isPending}
					>
						Cancel
					</Button>
					<Button
						onClick={handlePause}
						disabled={isPending || !isValidTimeout}
						loading={isPending}
					>
						Pause Flow Run
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};
