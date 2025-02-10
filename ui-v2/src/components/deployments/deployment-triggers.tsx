import { buildListAutomationsRelatedQuery } from "@/api/automations/automations";
import { Deployment } from "@/api/deployments";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Skeleton } from "../ui/skeleton";

type DeploymentTriggersProps = {
	deployment: Deployment;
};

const RelatedDeployments = ({ deployment }: DeploymentTriggersProps) => {
	const { data } = useQuery(
		buildListAutomationsRelatedQuery(`prefect.deployment.${deployment.id}`),
	);

	if (data) {
		return (
			<ul className="flex flex-col gap-1">
				{data.map((automation) => (
					<li key={automation.id}>
						<Link
							to="/automations/automation/$id"
							params={{ id: automation.id }}
							className="flex items-center text-xs"
						>
							<Icon id="Bot" className="mr-1 h-4 w-4" />
							<div>{automation.name}</div>
						</Link>
					</li>
				))}
			</ul>
		);
	}

	return (
		<ul className="flex flex-col gap-1">
			{Array.from({ length: 2 }).map((_, i) => (
				<li key={i}>
					<Skeleton className="h-4 w-full" />
				</li>
			))}
		</ul>
	);
};

export const DeploymentTriggers = ({ deployment }: DeploymentTriggersProps) => {
	return (
		<div className="flex flex-col gap-1">
			<div className="text-sm text-muted-foreground">Triggers</div>
			<div className="flex flex-col gap-2">
				<RelatedDeployments deployment={deployment} />
				<Link
					to="/automations/create"
					search={{
						actions: {
							type: "run-deployment",
							deploymentId: deployment.id,
							parameters: deployment.parameters,
						},
					}}
				>
					<Button size="sm">
						<Icon id="Plus" className="mr-2 h-4 w-4" /> Add
					</Button>
				</Link>
			</div>
		</div>
	);
};
