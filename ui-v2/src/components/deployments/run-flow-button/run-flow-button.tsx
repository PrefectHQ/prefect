import { Deployment } from "@/api/deployments";
import { useDeploymentCreateFlowRun } from "@/api/flow-runs";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { useToast } from "@/hooks/use-toast";
import { Link } from "@tanstack/react-router";

const DEPLOYMENT_QUICK_RUN_PAYLOAD = {
	state: {
		type: "SCHEDULED",
		message: "Run from the Prefect UI with defaults",
		state_details: {
			deferred: false,
			untrackable_result: false,
			pause_reschedule: false,
		},
	},
} as const;

export type RunFlowButtonProps = {
	deployment: Deployment;
};

export const RunFlowButton = ({ deployment }: RunFlowButtonProps) => {
	const { toast } = useToast();
	const { createDeploymentFlowRun, isPending } = useDeploymentCreateFlowRun();

	const handleClickQuickRun = (id: string) => {
		createDeploymentFlowRun(
			{
				id,
				...DEPLOYMENT_QUICK_RUN_PAYLOAD,
			},
			{
				onSuccess: (res) => {
					toast({
						action: (
							<Link to="/runs/flow-run/$id" params={{ id: res.id }}>
								<Button size="sm">View run</Button>
							</Link>
						),
						description: (
							<p>
								<span className="font-bold">{res.name}</span> scheduled to start{" "}
								<span className="font-bold">now</span>
							</p>
						),
					});
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while creating flow run.";
					console.error(message);
				},
			},
		);
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button loading={isPending}>
					Run <Icon className="ml-1 h-4 w-4" id="Play" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent>
				<DropdownMenuGroup>
					<DropdownMenuItem onClick={() => handleClickQuickRun(deployment.id)}>
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
	);
};
