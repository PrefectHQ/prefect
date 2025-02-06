import { Deployment } from "@/api/deployments";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import clsx from "clsx";

type DeploymentMetadataProps = {
	deployment: Deployment;
};

export const DeploymentMetadata = ({ deployment }: DeploymentMetadataProps) => {
	const METADATA_LIST = [
		{ key: "Flow ID", value: deployment.flow_id },
		{ key: "Deployment ID", value: deployment.id },
		{ key: "Deployment Version", value: deployment.version },
		{ key: "Storage Document ID", value: deployment.storage_document_id },
		{
			key: "Infrastructure Document ID",
			value: deployment.infrastructure_document_id,
		},
	] as const;

	return (
		<ul className="flex flex-col gap-3">
			{METADATA_LIST.map(({ key, value }) => (
				<li key={key} className="flex flex-col text-sm">
					<dl>
						<dt className="text-muted-foreground">{key}</dt>
						<dd className={clsx(!value && "text-muted-foreground")}>
							{value ?? "None"}
						</dd>
					</dl>
				</li>
			))}
			<li>
				<dl>
					<dt className="text-sm text-muted-foreground">Tags</dt>
					{deployment.tags ? (
						<dd aria-label={deployment.tags.toString()}>
							<TagBadgeGroup tags={deployment.tags} maxTagsDisplayed={4} />
						</dd>
					) : (
						<dd className="text-muted-foreground">None</dd>
					)}
				</dl>
			</li>
		</ul>
	);
};
