import { Suspense } from "react";

import type { WorkPool } from "@/api/work-pools";
import { FormattedDate } from "@/components/ui/formatted-date";
import { SchemaPropertyRenderer } from "@/components/ui/schema-property-renderer";
import { PollStatus } from "@/components/work-pools/poll-status";
import { WorkPoolStatusBadge } from "@/components/work-pools/work-pool-status-badge";
import { toTitleCase } from "@/lib/schema-utils";
import { cn } from "@/lib/utils";

import type { WorkPoolDetailsProps } from "./types";

// Helper components for field display
const None = () => <dd className="text-muted-foreground text-sm">None</dd>;
const FieldLabel = ({ children }: { children: React.ReactNode }) => (
	<dt className="text-sm text-muted-foreground">{children}</dt>
);
const FieldValue = ({ children }: { children: React.ReactNode }) => (
	<dd className="text-sm">{children}</dd>
);

// Basic Info Section Component
function BasicInfoSection({ workPool }: { workPool: WorkPool }) {
	const fields = [
		{
			field: "Status",
			ComponentValue: () => (
				<dd>
					<WorkPoolStatusBadge status={workPool.status || "NOT_READY"} />
				</dd>
			),
		},
		{
			field: "Description",
			ComponentValue: () =>
				workPool.description ? (
					<FieldValue>{workPool.description}</FieldValue>
				) : null,
		},
		{
			field: "Type",
			ComponentValue: () =>
				workPool.type ? (
					<FieldValue>{toTitleCase(workPool.type)}</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Concurrency Limit",
			ComponentValue: () => (
				<FieldValue>
					{workPool.concurrency_limit
						? String(workPool.concurrency_limit)
						: "Unlimited"}
				</FieldValue>
			),
		},
		{
			field: "Created",
			ComponentValue: () =>
				workPool.created ? (
					<FieldValue>
						<FormattedDate date={workPool.created} />
					</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Last Updated",
			ComponentValue: () =>
				workPool.updated ? (
					<FieldValue>
						<FormattedDate date={workPool.updated} />
					</FieldValue>
				) : (
					<None />
				),
		},
	].filter(({ ComponentValue }) => ComponentValue() !== null);

	return (
		<div>
			<h3 className="mb-4 text-lg font-semibold">Basic Information</h3>
			<ul className="flex flex-col gap-3">
				{fields.map(({ field, ComponentValue }) => (
					<li key={field}>
						<dl>
							<FieldLabel>{field}</FieldLabel>
							<ComponentValue />
						</dl>
					</li>
				))}
			</ul>
		</div>
	);
}

// Job Template Section Component
function JobTemplateSection({ workPool }: { workPool: WorkPool }) {
	// Check if work pool has base job template
	const baseJobTemplate = workPool.base_job_template;

	if (!baseJobTemplate?.job_configuration) {
		return null;
	}

	// Convert job template to schema format
	const schema = {
		properties: baseJobTemplate.variables || {},
	};

	const data = baseJobTemplate.job_configuration as Record<string, unknown>;

	return (
		<div>
			<h3 className="mb-4 text-lg font-semibold">Base Job Template</h3>
			<SchemaPropertyRenderer schema={schema} data={data} />
		</div>
	);
}

export function WorkPoolDetails({
	workPool,
	alternate = false,
	className,
}: WorkPoolDetailsProps) {
	const spacing = alternate ? "space-y-4" : "space-y-6";

	return (
		<div className={cn(spacing, className)}>
			<BasicInfoSection workPool={workPool} />

			<Suspense
				fallback={
					<div className="text-muted-foreground">Loading poll status...</div>
				}
			>
				<PollStatus workPoolName={workPool.name} />
			</Suspense>

			{workPool.base_job_template?.job_configuration && (
				<JobTemplateSection workPool={workPool} />
			)}
		</div>
	);
}
