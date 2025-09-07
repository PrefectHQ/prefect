import { useFormContext } from "react-hook-form";
import { Card, CardContent, CardDescription } from "@/components/ui/card";
import { BaseJobTemplateFormSection } from "./base-job-template-form-section";
import type { WorkerBaseJobTemplate } from "./schema";

export function InfrastructureConfigurationStep() {
	const form = useFormContext();
	const baseJobTemplate = form.watch(
		"baseJobTemplate",
	) as WorkerBaseJobTemplate;

	return (
		<div className="space-y-6">
			<Card>
				<CardContent>
					<CardDescription>
						The fields below control the default values for the base job
						template. These values can be overridden by deployments.
						<br />
						<br />A work pools job template controls infrastructure
						configuration for all flow runs in the work pool, and specifies the
						configuration that can be overridden by deployments.
					</CardDescription>
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
