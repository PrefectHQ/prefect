import { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Typography } from "@/components/ui/typography";
import { useMemo } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArtifactDetailHeader } from "./artifact-detail-header";
import { ArtifactDataDisplay } from "./artifact-raw-data-display";
import { DetailImage } from "./detail-image";
import { DetailMarkdown } from "./detail-markdown";
import { DetailProgress } from "./detail-progress";
import { DetailTable } from "./detail-table";
import { RightTable } from "./right-table";

export type ArtifactDetailPageProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactDetailPage = ({ artifact }: ArtifactDetailPageProps) => {
	const mapArtifactHoc = useMemo(() => {
		switch (artifact.type) {
			case "markdown":
			case "link":
				return <DetailMarkdown markdown={artifact.data as string} />;
			case "image":
				return <DetailImage url={artifact.data as string} />;
			case "progress":
				return <DetailProgress progress={artifact.data as number} />;
			case "table":
				return <DetailTable tableData={artifact.data as string} />;
			default:
				return <pre>{JSON.stringify(artifact.data, null, 2)}</pre>;
		}
	}, [artifact]);
	return (
		<div>
			<ArtifactDetailHeader artifact={artifact} />
			<div className="flex flex-row gap-4 justify-between">
				<div className="flex-grow">
					{artifact.description && (
						<div>
							<Typography
								variant="h2"
								className="my-4 font-bold prose lg:prose-xl"
							>
								<Markdown remarkPlugins={[remarkGfm]}>
									{artifact.description}
								</Markdown>
							</Typography>
						</div>
					)}
					<hr />
					{mapArtifactHoc}
					<ArtifactDataDisplay artifact={artifact} />
				</div>
				<RightTable artifact={artifact} />
			</div>
		</div>
	);
};
