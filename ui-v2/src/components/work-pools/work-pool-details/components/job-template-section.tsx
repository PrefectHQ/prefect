import type { WorkPool } from "@/api/work-pools";
import { SchemaPropertyRenderer } from "@/components/ui/schema-property-renderer";

interface JobTemplateSectionProps {
	workPool: WorkPool;
}

export function JobTemplateSection({ workPool }: JobTemplateSectionProps) {
	// Check if work pool has base job template
	const baseJobTemplate = workPool.base_job_template;

	if (!baseJobTemplate?.job_configuration) {
		return null;
	}

	// Convert job template to schema format
	const schema = {
		properties: baseJobTemplate.variables || ({} as Record<string, any>),
	};

	const data =
		baseJobTemplate.job_configuration || ({} as Record<string, unknown>);

	return (
		<div>
			<h3 className="mb-4 text-lg font-semibold">Base Job Template</h3>
			<SchemaPropertyRenderer schema={schema} data={data} />
		</div>
	);
}
