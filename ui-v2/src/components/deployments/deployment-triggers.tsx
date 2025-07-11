import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import type { Automation } from "@/api/automations";
import { buildListAutomationsRelatedQuery } from "@/api/automations/automations";
import type { Deployment } from "@/api/deployments";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";

type DeploymentTriggersProps = {
	deployment: Deployment;
};

export const DeploymentTriggers = ({ deployment }: DeploymentTriggersProps) => {
	return (
		<Suspense fallback={<LoadingSkeleton numSkeletons={2} />}>
			<DeploymentTriggersImplementation deployment={deployment} />
		</Suspense>
	);
};

export const DeploymentTriggersImplementation = ({
	deployment,
}: DeploymentTriggersProps) => {
	const { data: automations } = useSuspenseQuery(
		buildListAutomationsRelatedQuery(`prefect.deployment.${deployment.id}`),
	);

	return (
		<div className="flex flex-col gap-1">
			<div className="text-sm text-muted-foreground">Triggers</div>
			<div className="flex flex-col gap-2">
				<RelatedDeployments automations={automations} />
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
						<Icon id="Plus" className="mr-2 size-4" /> Add
					</Button>
				</Link>
			</div>
		</div>
	);
};

type RelatedDeploymentsProps = {
	automations: Array<Automation>;
};
const RelatedDeployments = ({ automations }: RelatedDeploymentsProps) => {
	return (
		<ul className="flex flex-col gap-1">
			{automations.map((automation) => (
				<li key={automation.id}>
					<Link
						to="/automations/automation/$id"
						params={{ id: automation.id }}
						className="flex items-center text-xs"
					>
						<Icon id="Bot" className="mr-1 size-4" />
						<div>{automation.name}</div>
					</Link>
				</li>
			))}
		</ul>
	);
};

type LoadingSkeletonProps = {
	numSkeletons?: number;
};
const LoadingSkeleton = ({ numSkeletons = 1 }: LoadingSkeletonProps) => (
	<ul className="flex flex-col gap-1">
		{Array.from({ length: numSkeletons }).map((_, i) => (
			// biome-ignore lint/suspicious/noArrayIndexKey: okay for static skeleton list
			<li key={i}>
				<Skeleton className="h-4 w-full" />
			</li>
		))}
	</ul>
);
