import { Link } from "@tanstack/react-router";
import type { Deployment } from "@/api/deployments";
import type { FlowRun } from "@/api/flow-runs";
import { QuickRunParametersDialog } from "@/components/deployments/quick-run-parameters-dialog";
import { useQuickRun } from "@/components/deployments/use-quick-run";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";

export type RunFlowButtonProps = {
	deployment: Deployment;
	onRunCreated?: (flowRun: FlowRun) => void;
};

export const RunFlowButton = ({
	deployment,
	onRunCreated,
}: RunFlowButtonProps) => {
	const { onQuickRun, isPending, parametersDialogState } = useQuickRun(
		deployment,
		{ onRunCreated },
	);

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild disabled={isPending}>
					<Button loading={isPending}>
						Run <Icon className="ml-1 size-4" id="Play" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent>
					<DropdownMenuGroup>
						<DropdownMenuItem disabled={isPending} onClick={onQuickRun}>
							Quick run
						</DropdownMenuItem>
						<Link
							to="/deployments/deployment/$id/run"
							params={{ id: deployment.id }}
							search={{ parameters: deployment.parameters }}
						>
							<DropdownMenuItem>Custom run</DropdownMenuItem>
						</Link>
					</DropdownMenuGroup>
				</DropdownMenuContent>
			</DropdownMenu>
			{parametersDialogState.open && (
				<QuickRunParametersDialog
					deployment={deployment}
					onRunCreated={onRunCreated}
					{...parametersDialogState}
				/>
			)}
		</>
	);
};
