import { Link } from "@tanstack/react-router";
import type { Deployment } from "@/api/deployments";
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
};

export const RunFlowButton = ({ deployment }: RunFlowButtonProps) => {
	const { onQuickRun, isPending } = useQuickRun();

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button loading={isPending}>
					Run <Icon className="ml-1 size-4" id="Play" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent>
				<DropdownMenuGroup>
					<DropdownMenuItem onClick={() => onQuickRun(deployment.id)}>
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
