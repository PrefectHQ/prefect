import type { WorkPool } from "@/api/work-pools";
import { FormattedDate } from "@/components/ui/formatted-date";
import { WorkPoolStatusBadge } from "@/components/work-pools/work-pool-status-badge";
import { toTitleCase } from "@/lib/schema-utils";

interface BasicInfoSectionProps {
	workPool: WorkPool;
}

const None = () => <dd className="text-muted-foreground text-sm">None</dd>;
const FieldLabel = ({ children }: { children: React.ReactNode }) => (
	<dt className="text-sm text-muted-foreground">{children}</dt>
);
const FieldValue = ({ children }: { children: React.ReactNode }) => (
	<dd className="text-sm">{children}</dd>
);

export function BasicInfoSection({ workPool }: BasicInfoSectionProps) {
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
