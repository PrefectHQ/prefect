import { useSuspenseQuery } from "@tanstack/react-query";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { CreateFlowRunForm } from "@/components/deployments/create-flow-run-form";
import { DeploymentActionHeader } from "./deployment-action-header";
import { DeploymentLinks } from "./deployment-links";

type CustomRunPageProps = {
	id: string;
	overrideParameters: Record<string, unknown> | undefined;
	additionalOptions?: Record<string, unknown>;
};

export const CustomRunPage = ({
	id,
	overrideParameters,
	additionalOptions,
}: CustomRunPageProps) => {
	const { data } = useSuspenseQuery(buildDeploymentDetailsQuery(id));

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<DeploymentActionHeader deployment={data} action="Run" />
				<DeploymentLinks deployment={data} />
			</div>
			<CreateFlowRunForm
				key={data.id}
				deployment={data}
				overrideParameters={overrideParameters}
				overrideAdditionalOptions={additionalOptions}
			/>
		</div>
	);
};
