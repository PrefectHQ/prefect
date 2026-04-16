import type { Deployment } from "@/api/deployments";
import { DocsLink } from "@/components/ui/docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { LazyMarkdown } from "@/components/ui/lazy-markdown";

type DeploymentDescriptionProps = {
	deployment: Deployment;
};

const isDeploymentDeprecated = (deployment: Deployment): boolean =>
	deployment.entrypoint === "" || deployment.entrypoint === null;

export const DeploymentDescription = ({
	deployment,
}: DeploymentDescriptionProps) => {
	if (isDeploymentDeprecated(deployment)) {
		return <DeploymentDeprecatedMessage />;
	}

	if (!deployment.description) {
		return <DeploymentDescriptionEmptyState />;
	}

	return (
		<div className="prose max-w-none">
			<LazyMarkdown>{deployment.description}</LazyMarkdown>
		</div>
	);
};

const DeploymentDeprecatedMessage = () => (
	<EmptyState>
		<EmptyStateIcon id="CircleAlert" />
		<EmptyStateTitle>This deployment is deprecated</EmptyStateTitle>
		<EmptyStateDescription>
			With the General Availability release of Prefect 2, we modified the
			approach to creating deployments.
		</EmptyStateDescription>
		<EmptyStateActions>
			<DocsLink id="deployments-guide" />
		</EmptyStateActions>
	</EmptyState>
);

const DeploymentDescriptionEmptyState = () => (
	<EmptyState>
		<EmptyStateIcon id="AlignJustify" />
		<EmptyStateTitle>Add deployment description</EmptyStateTitle>
		<EmptyStateDescription>
			You can do so by adding a description as part of your deployment
			configuration.
		</EmptyStateDescription>
		<EmptyStateActions>
			<DocsLink id="deployments-guide" />
		</EmptyStateActions>
	</EmptyState>
);
