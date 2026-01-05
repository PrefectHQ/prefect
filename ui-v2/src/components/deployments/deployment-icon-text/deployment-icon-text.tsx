import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import {
	buildDeploymentDetailsQuery,
	type Deployment,
} from "@/api/deployments";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";

type DeploymentIconTextBaseProps = {
	className?: string;
	iconSize?: number;
	onClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
};

type DeploymentIconTextWithIdProps = DeploymentIconTextBaseProps & {
	deploymentId: string;
	deployment?: never;
};

type DeploymentIconTextWithDeploymentProps = DeploymentIconTextBaseProps & {
	deployment: Deployment;
	deploymentId?: never;
};

type DeploymentIconTextProps =
	| DeploymentIconTextWithIdProps
	| DeploymentIconTextWithDeploymentProps;

export const DeploymentIconText = (props: DeploymentIconTextProps) => {
	if ("deployment" in props && props.deployment) {
		return (
			<DeploymentIconTextPresentational
				{...props}
				deployment={props.deployment}
			/>
		);
	}

	return (
		<Suspense fallback={<Skeleton className="h-4 w-full" />}>
			<DeploymentIconTextFetched {...props} deploymentId={props.deploymentId} />
		</Suspense>
	);
};

type DeploymentIconTextFetchedProps = DeploymentIconTextBaseProps & {
	deploymentId: string;
};

const DeploymentIconTextFetched = ({
	deploymentId,
	className,
	iconSize,
	onClick,
}: DeploymentIconTextFetchedProps) => {
	const { data: deployment } = useSuspenseQuery(
		buildDeploymentDetailsQuery(deploymentId),
	);

	return (
		<DeploymentIconTextPresentational
			deployment={deployment}
			className={className}
			iconSize={iconSize}
			onClick={onClick}
		/>
	);
};

type DeploymentIconTextPresentationalProps = DeploymentIconTextBaseProps & {
	deployment: Deployment;
};

const DeploymentIconTextPresentational = ({
	deployment,
	className,
	iconSize,
	onClick,
}: DeploymentIconTextPresentationalProps) => {
	return (
		<Link
			to="/deployments/deployment/$id"
			params={{ id: deployment.id }}
			className={className ?? "flex items-center gap-1"}
			onClick={onClick}
		>
			<Icon
				id="Rocket"
				size={iconSize}
				className={iconSize ? undefined : "size-4"}
			/>
			{deployment.name}
		</Link>
	);
};
