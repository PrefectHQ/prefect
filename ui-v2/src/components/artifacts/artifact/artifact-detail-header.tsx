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
import { Typography } from "@/components/ui/typography";

export type ArtifactDetailHeaderProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactDetailHeader = ({
	artifact,
}: ArtifactDetailHeaderProps) => {
	let header = <></>;
	if (artifact.key) {
		header = (
			<div className="flex items-center gap-2">
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem>
							<BreadcrumbLink
								to="/artifacts/key/$key"
								params={{ key: artifact.key }}
								className="text-xl font-semibold"
							>
								{artifact.key}
							</BreadcrumbLink>
						</BreadcrumbItem>
						<BreadcrumbSeparator />
						<BreadcrumbItem className="text-xl font-semibold">
							{artifact.id}
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
			</div>
		);
	} else {
		header = (
			<div className="flex items-center gap-2">
				<Breadcrumb>
					<BreadcrumbList>
						{artifact.flow_run && (
							<>
								<BreadcrumbItem>
									<BreadcrumbLink
										to="/runs/flow-run/$id"
										params={{ id: artifact.flow_run_id ?? "" }}
										className="text-xl font-semibold"
									>
										{artifact.flow_run.name}
									</BreadcrumbLink>
								</BreadcrumbItem>
								<BreadcrumbSeparator />
							</>
						)}
						{artifact.task_run && (
							<>
								<BreadcrumbItem>
									<BreadcrumbLink
										to="/runs/task-run/$id"
										params={{ id: artifact.task_run_id ?? "" }}
										className="text-xl font-semibold"
									>
										{artifact.task_run.name}
									</BreadcrumbLink>
								</BreadcrumbItem>
								<BreadcrumbSeparator />
							</>
						)}
						<BreadcrumbItem className="text-xl font-semibold">
							{artifact.id}
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
			</div>
		);
	}
	return (
		<>
			<div className="flex items-center justify-between">
				{header}
				<DocsLink id="artifacts-guide" label="Documentation" />
			</div>
			{artifact.description && (
				<div className="">
					<Typography variant="h2" className="my-4 font-bold prose lg:prose-xl">
						<LazyMarkdown>{artifact.description}</LazyMarkdown>
					</Typography>
				</div>
			)}
			<hr />
		</>
	);
};
