import { Link } from "@tanstack/react-router";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { DocsLink } from "@/components/ui/docs-link";
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
			<div className="flex items-center ">
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem className="text-xl text-blue-700 hover:underline">
							<Link to={"/artifacts/key/$key"} params={{ key: artifact.key }}>
								{artifact.key}
							</Link>
						</BreadcrumbItem>
						<BreadcrumbSeparator>/</BreadcrumbSeparator>
						<BreadcrumbItem className="text-xl font-bold text-black">
							{artifact.id}
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
			</div>
		);
	} else {
		header = (
			<div className="flex items-center ">
				<Breadcrumb>
					<BreadcrumbList>
						{artifact.flow_run && (
							<>
								<BreadcrumbItem>
									<Typography
										variant="bodyLarge"
										className="text-blue-700 hover:underline"
									>
										<Link
											to={"/runs/flow-run/$id"}
											params={{ id: artifact.flow_run_id ?? "" }}
										>
											{artifact.flow_run.name}
										</Link>
									</Typography>
								</BreadcrumbItem>
								<BreadcrumbSeparator>/</BreadcrumbSeparator>
							</>
						)}
						{artifact.task_run && (
							<>
								<BreadcrumbItem>
									<Typography
										variant="bodyLarge"
										className="text-blue-700 hover:underline"
									>
										<Link
											to={"/runs/task-run/$id"}
											params={{ id: artifact.task_run_id ?? "" }}
										>
											{artifact.task_run.name}
										</Link>
									</Typography>
								</BreadcrumbItem>
								<BreadcrumbSeparator>/</BreadcrumbSeparator>
							</>
						)}
						<BreadcrumbItem className="text-xl font-bold text-black">
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
						<Markdown remarkPlugins={[remarkGfm]}>
							{artifact.description}
						</Markdown>
					</Typography>
				</div>
			)}
			<hr />
		</>
	);
};
