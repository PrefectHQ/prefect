import { useMemo } from "react";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { KeyValue } from "@/components/ui/key-value";
import { formatDate } from "@/utils/date";

type ArtifactSectionProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactSection = ({ artifact }: ArtifactSectionProps) => {
	const createdDate = useMemo(() => {
		if (!artifact.created) return null;
		return formatDate(artifact.created, "dateTime");
	}, [artifact.created]);

	return (
		<div className="mt-4">
			<p className="text-base font-semibold">Artifact</p>

			<div className="mt-3 flex flex-col gap-3">
				<KeyValue
					label="Key"
					value={<span className="font-mono">{artifact.key ?? "None"}</span>}
				/>

				<KeyValue
					label="Type"
					value={<span className="font-mono">{artifact.type ?? "None"}</span>}
				/>

				<KeyValue
					label="Created"
					value={<span>{createdDate ?? "None"}</span>}
				/>
			</div>
		</div>
	);
};
