import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { DocsLink } from "@/components/ui/docs-link";
import { LazyMarkdown } from "@/components/ui/lazy-markdown";

export type ArtifactDetailHeaderProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactDetailHeader = ({
	artifact,
}: ArtifactDetailHeaderProps) => {
	const header = artifact.key ? (
		<div className="flex items-center gap-2 min-w-0">
			<Breadcrumb className="min-w-0">
				<BreadcrumbList className="flex-nowrap">
					<BreadcrumbItem className="min-w-0">
						<BreadcrumbLink
							to="/artifacts/key/$key"
							params={{ key: artifact.key }}
							className="text-xl font-semibold truncate block"
							title={artifact.key}
						>
							{artifact.key}
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem className="text-xl font-semibold min-w-0">
						<span className="font-mono truncate block" title={artifact.id}>
							{artifact.id}
						</span>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</div>
	) : (
		<div className="flex items-center gap-2 min-w-0">
			<Breadcrumb className="min-w-0">
				<BreadcrumbList className="flex-nowrap">
					{artifact.flow_run && (
						<>
							<BreadcrumbItem className="min-w-0">
								<BreadcrumbLink
									to="/runs/flow-run/$id"
									params={{ id: artifact.flow_run_id ?? "" }}
									className="text-xl font-semibold truncate block"
									title={artifact.flow_run.name}
								>
									{artifact.flow_run.name}
								</BreadcrumbLink>
							</BreadcrumbItem>
							<BreadcrumbSeparator />
						</>
					)}
					{artifact.task_run && (
						<>
							<BreadcrumbItem className="min-w-0">
								<BreadcrumbLink
									to="/runs/task-run/$id"
									params={{ id: artifact.task_run_id ?? "" }}
									className="text-xl font-semibold truncate block"
									title={artifact.task_run.name}
								>
									{artifact.task_run.name}
								</BreadcrumbLink>
							</BreadcrumbItem>
							<BreadcrumbSeparator />
						</>
					)}
					<BreadcrumbItem className="text-xl font-semibold min-w-0">
						<span className="font-mono truncate block" title={artifact.id}>
							{artifact.id}
						</span>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</div>
	);
	return (
		<>
			<div className="flex items-center justify-between">
				{header}
				<DocsLink id="artifacts-guide" label="Documentation" />
			</div>
			{artifact.description && (
				<div className="text-sm text-muted-foreground my-2">
					<LazyMarkdown>{artifact.description}</LazyMarkdown>
				</div>
			)}
			<hr />
		</>
	);
};
