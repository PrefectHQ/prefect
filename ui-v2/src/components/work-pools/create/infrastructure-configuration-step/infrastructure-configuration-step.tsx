import { useFormContext } from "react-hook-form";
import { Card, CardContent, CardDescription } from "@/components/ui/card";
import { BaseJobTemplateFormSection } from "./base-job-template-form-section";
import type { WorkerBaseJobTemplate } from "./schema";

const INFRASTRUCTURE_INFO_TEXT = `
The fields below control the default values for the base job template. These values can be overridden by deployments.

A work pool's job template controls infrastructure configuration for all flow runs in the work pool, and specifies the configuration that can be overridden by deployments.
`;

export function InfrastructureConfigurationStep() {
	const form = useFormContext();
	const baseJobTemplate = form.watch(
		"baseJobTemplate",
	) as WorkerBaseJobTemplate;

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
					form.setValue("baseJobTemplate", value as unknown);
				}}
			/>
		</div>
	);
}
