import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { QuickRunParametersDialog } from "@/components/deployments/quick-run-parameters-dialog";
import { useQuickRun } from "@/components/deployments/use-quick-run";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { WorkPoolIconText } from "@/components/work-pools/work-pool-icon-text";
import type { CellContext } from "@/lib/tanstack-table";

type FlowRun = components["schemas"]["FlowRunResponse"];
type Deployment = components["schemas"]["DeploymentResponse"];

export const DeploymentCell = ({ row }: { row: { original: FlowRun } }) => {
	const deploymentId = row.original.deployment_id;
	const { data: deployment } = useQuery({
		queryKey: ["deployment", deploymentId],
		queryFn: async () =>
			(await getQueryService()).GET("/deployments/{id}", {
				params: { path: { id: deploymentId as string } },
			}),
		enabled: !!deploymentId,
	});
	return deployment?.data?.name;
};

export const WorkPoolCell = ({ row }: { row: { original: FlowRun } }) => {
	const deploymentId = row.original.deployment_id;
	const { data: deployment } = useQuery({
		queryKey: ["deployment", deploymentId],
		queryFn: async () =>
			(await getQueryService()).GET("/deployments/{id}", {
				params: { path: { id: deploymentId as string } },
			}),
		enabled: !!deploymentId,
	});

	const workPoolName = deployment?.data?.work_pool_name;
	if (!workPoolName) {
		return null;
	}
	return <WorkPoolIconText workPoolName={workPoolName} />;
};

export const DeploymentActionsCell = ({
	row,
}: CellContext<Deployment, unknown>) => {
	const { id, parameters } = row.original;
	const { onQuickRun, isPending, parametersDialogState } = useQuickRun(
		row.original,
	);

	if (!id) return null;

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="ghost" size="icon">
						<span className="sr-only">Open menu</span>
						<Icon id="MoreHorizontal" className="size-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
					<DropdownMenuItem disabled={isPending} onClick={onQuickRun}>
						Quick Run
					</DropdownMenuItem>
					<DropdownMenuItem>
						<Link
							to="/deployments/deployment/$id/run"
							params={{ id }}
							search={{ parameters }}
						>
							Custom Run
						</Link>
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() => {
							void navigator.clipboard.writeText(id);
							toast.success("ID copied");
						}}
					>
						Copy ID
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
			{parametersDialogState.open && (
				<QuickRunParametersDialog
					deployment={row.original}
					{...parametersDialogState}
				/>
			)}
		</>
	);
};
