import type { Deployment } from "@/api/deployments";
import { StatusBadge } from "@/components/ui/status-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { cn } from "@/utils";

type DeploymentMetadataProps = {
	deployment: Deployment;
};

const None = () => <dd className="text-muted-foreground text-sm">None</dd>;
const FieldLabel = ({ children }: { children: React.ReactNode }) => (
	<dt className="text-sm text-muted-foreground">{children}</dt>
);

const FieldValue = ({
	className,
	children,
}: {
	className?: string;
	children: React.ReactNode;
}) => <dd className={cn("text-sm", className)}>{children}</dd>;
export const DeploymentMetadata = ({ deployment }: DeploymentMetadataProps) => {
	const TOP_FIELDS = [
		{
			field: "Status",
			ComponentValue: () =>
				deployment.status ? (
					<dd>
						<StatusBadge status={deployment.status} />
					</dd>
				) : (
					<None />
				),
		},
		{
			field: "Created",
			ComponentValue: () =>
				deployment.created ? (
					<FieldValue className="font-mono">{deployment.created}</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Updated",
			ComponentValue: () =>
				deployment.updated ? (
					<FieldValue className="font-mono">{deployment.updated}</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Entrypoint",
			ComponentValue: () =>
				deployment.entrypoint ? (
					<FieldValue>{deployment.entrypoint}</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Path",
			ComponentValue: () =>
				deployment.path ? <FieldValue>{deployment.path}</FieldValue> : <None />,
		},
		{
			field: "Concurrency Limit",
			ComponentValue: () =>
				deployment.global_concurrency_limit ? (
					<FieldValue>{deployment.global_concurrency_limit.limit}</FieldValue>
				) : (
					<None />
				),
		},
	] as const;

	const BOTTOM_FIELDS = [
		{
			field: "Flow ID",
			ComponentValue: () => <FieldValue>{deployment.flow_id}</FieldValue>,
		},
		{
			field: "Deployment ID",
			ComponentValue: () => <FieldValue>{deployment.id}</FieldValue>,
		},
		{
			field: "Deployment Version",
			ComponentValue: () =>
				deployment.version ? (
					<FieldValue>{deployment.version}</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Storage Document ID",
			ComponentValue: () =>
				deployment.storage_document_id ? (
					<FieldValue>{deployment.storage_document_id}</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Infrastructure Document ID",
			ComponentValue: () =>
				deployment.infrastructure_document_id ? (
					<FieldValue>{deployment.infrastructure_document_id}</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Tags",
			ComponentValue: () =>
				deployment.tags && deployment.tags.length > 0 ? (
					<dd>
						<TagBadgeGroup tags={deployment.tags} maxTagsDisplayed={4} />
					</dd>
				) : (
					<None />
				),
		},
	];

	return (
		<div>
			<ul className="flex flex-col gap-3">
				{TOP_FIELDS.map(({ field, ComponentValue }) => (
					<li key={field}>
						<dl>
							<FieldLabel>{field}</FieldLabel>
							<ComponentValue />
						</dl>
					</li>
				))}
			</ul>
			<hr className="my-3" />
			<ul className="flex flex-col gap-3">
				{BOTTOM_FIELDS.map(({ field, ComponentValue }) => (
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
};
