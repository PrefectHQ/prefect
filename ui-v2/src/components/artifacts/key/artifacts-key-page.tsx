import { Artifact } from "@/api/artifacts";
import { ArtifactsKeyHeader } from "./artifacts-key-header";

interface ArtifactsKeyPageProps {
	artifactKey: string;
	artifacts: Artifact[];
}

export const ArtifactsKeyPage = ({
	artifactKey,
	artifacts,
}: ArtifactsKeyPageProps) => {
	return (
		<div>
			<ArtifactsKeyHeader
				artifactKey={artifactKey}
				pageHeader={artifacts[0]?.description ?? undefined}
			/>
			<p>{artifactKey}</p>
			{artifacts.map((artifact) => (
				<div key={artifact.id}>{artifact.updated}</div>
			))}
		</div>
	);
};
