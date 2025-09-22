import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import type { WorkPool } from "@/api/work-pools";
import { buildListWorkPoolWorkersQuery } from "@/api/work-pools";
import type { SchemaProperty } from "@/components/schemas/schema-display";
import { FormattedDate } from "@/components/ui/formatted-date";
import { Separator } from "@/components/ui/separator";
import { WorkPoolStatusBadge } from "@/components/work-pools/work-pool-status-badge";
import { cn, titleCase } from "@/utils";

type WorkPoolDetailsProps = {
	workPool: WorkPool;
	alternate?: boolean;
	className?: string;
};

// Helper components for field display
const None = () => <dd className="text-muted-foreground text-sm">None</dd>;
const FieldLabel = ({ children }: { children: React.ReactNode }) => (
	<dt className="text-sm text-muted-foreground">{children}</dt>
);
const FieldValue = ({
	children,
	className,
}: {
	children: React.ReactNode;
	className?: string;
}) => <dd className={cn("text-sm", className)}>{children}</dd>;

// Basic Info Section Component
function BasicInfoSection({ workPool }: { workPool: WorkPool }) {
	const { data: workers = [], isLoading } = useQuery(
		buildListWorkPoolWorkersQuery(workPool.name),
	);

	const lastPolled = useMemo(() => {
		if (isLoading) return null;
		if (workers.length === 0) return null;

		const heartbeats = workers
			.map((w) => w.last_heartbeat_time)
			.filter((time): time is string => Boolean(time))
			.sort((a, b) => new Date(b).getTime() - new Date(a).getTime());

		return heartbeats[0] || null;
	}, [workers, isLoading]);

	const fields = [
		{
			field: "Status",
			ComponentValue: () => (
				<dd>
					<WorkPoolStatusBadge
						status={
							(workPool.status?.toLowerCase() as
								| "ready"
								| "paused"
								| "not_ready") || "not_ready"
						}
					/>
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
					<FieldValue>{titleCase(workPool.type)}</FieldValue>
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
			field: "Last Polled",
			ComponentValue: () =>
				lastPolled ? (
					<FieldValue>
						<FormattedDate date={lastPolled} />
					</FieldValue>
				) : workers.length === 0 ? null : (
					<FieldValue className="text-muted-foreground">
						No recent activity
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

	if (isLoading) {
		return (
			<div className="text-muted-foreground text-sm">
				Loading work pool details...
			</div>
		);
	}

	return (
		<div>
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

	if (
		!baseJobTemplate?.variables ||
		typeof baseJobTemplate.variables !== "object" ||
		!("properties" in baseJobTemplate.variables) ||
		!baseJobTemplate.variables.properties
	) {
		return null;
	}

	const properties = baseJobTemplate.variables.properties as Record<
		string,
		SchemaProperty
	>;

	// Helper function to format field names (from property title or key)
	const formatFieldName = (key: string, property: SchemaProperty): string => {
		return (
			property.title ||
			key
				.split("_")
				.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
				.join(" ")
		);
	};

	// Helper function to format field values
	const formatValue = (value: unknown): string => {
		if (value === null || value === undefined) {
			return "None";
		}
		if (typeof value === "boolean") {
			return value.toString();
		}
		if (Array.isArray(value)) {
			return value.length > 0 ? value.join(", ") : "None";
		}
		if (typeof value === "object") {
			return JSON.stringify(value);
		}
		// At this point, value is a primitive (string, number, bigint, symbol)
		return String(value as string | number | bigint | symbol);
	};

	return (
		<div>
			<h3 className="mb-4 text-md">Base Job Configuration</h3>
			<ul className="flex flex-col gap-3">
				{Object.entries(properties).map(([key, property]) => {
					const value = property.default ?? null;
					return (
						<li key={key} className="flex flex-col gap-1 text-sm">
							<span className="text-muted-foreground font-medium">
								{formatFieldName(key, property)}
							</span>
							<span className="break-words">{formatValue(value)}</span>
						</li>
					);
				})}
			</ul>
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

			{Boolean(
				workPool.base_job_template?.variables &&
					typeof workPool.base_job_template.variables === "object" &&
					"properties" in workPool.base_job_template.variables &&
					workPool.base_job_template.variables.properties &&
					Object.keys(
						workPool.base_job_template.variables.properties as Record<
							string,
							unknown
						>,
					).length > 0,
			) && (
				<>
					<Separator />
					<JobTemplateSection workPool={workPool} />
				</>
			)}
		</div>
	);
}
