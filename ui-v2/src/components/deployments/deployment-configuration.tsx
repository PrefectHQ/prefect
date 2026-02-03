import type { Deployment } from "@/api/deployments";
import { LazyJsonInput as JsonInput } from "@/components/ui/json-input-lazy";

type DeploymentConfigurationProps = {
	deployment: Deployment;
};

export const DeploymentConfiguration = ({
	deployment,
}: DeploymentConfigurationProps) => {
	const jobVariablesDisplay = JSON.stringify(
		deployment.job_variables ?? {},
		null,
		2,
	);
	const pullStepsDisplay = JSON.stringify(deployment.pull_steps ?? [], null, 2);
	return (
		<div className="flex flex-col gap-4">
			<h4 className="text-xl font-semibold tracking-tight">Job Variables</h4>
			<JsonInput copy disabled hideLineNumbers value={jobVariablesDisplay} />
			<h4 className="text-xl font-semibold tracking-tight">Pull Steps</h4>
			<JsonInput copy disabled hideLineNumbers value={pullStepsDisplay} />
		</div>
	);
};
