import type { Deployment } from "@/api/deployments";
import { JsonInput } from "@/components/ui/json-input";
import { Typography } from "@/components/ui/typography";

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
			<Typography variant="h4">Job Variables</Typography>
			<JsonInput copy disabled hideLineNumbers value={jobVariablesDisplay} />
			<Typography variant="h4">Pull Steps </Typography>
			<JsonInput copy disabled hideLineNumbers value={pullStepsDisplay} />
		</div>
	);
};
