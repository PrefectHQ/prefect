import { useFormContext } from "react-hook-form";
import { Card, CardContent, CardDescription } from "@/components/ui/card";
import { BaseJobTemplateFormSection } from "./base-job-template-form-section";

const PREFECT_AGENT_TYPE = "prefect-agent";

const INFRASTRUCTURE_INFO_TEXT = `
The fields below control the default values for the base job template. These values can be overridden by deployments.

A work pool's job template controls infrastructure configuration for all flow runs in the work pool, and specifies the configuration that can be overridden by deployments.
`;

const PREFECT_AGENT_INFO_TEXT = `
Prefect Agent work pools don't require infrastructure configuration. The agent will handle job execution directly.
`;

export function InfrastructureConfigurationStep() {
	const form = useFormContext();
	const workPoolType = form.watch("type");
	const baseJobTemplate = form.watch("baseJobTemplate");

	const isPrefectAgent = workPoolType === PREFECT_AGENT_TYPE;

	if (isPrefectAgent) {
		return (
			<Card>
				<CardContent>
					<CardDescription>{PREFECT_AGENT_INFO_TEXT}</CardDescription>
				</CardContent>
			</Card>
		);
	}

	return (
		<div className="space-y-6">
			<Card>
				<CardContent>
					<CardDescription>{INFRASTRUCTURE_INFO_TEXT}</CardDescription>
				</CardContent>
			</Card>

			<BaseJobTemplateFormSection
				baseJobTemplate={baseJobTemplate}
				onBaseJobTemplateChange={(value) => {
					form.setValue("baseJobTemplate", value);
				}}
			/>
		</div>
	);
}
