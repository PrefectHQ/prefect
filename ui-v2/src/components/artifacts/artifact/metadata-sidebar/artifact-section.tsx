import { useMemo } from "react";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Typography } from "@/components/ui/typography";
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
			<Typography variant="bodyLarge" className="font-bold">
				Artifact
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Key
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 text-foreground"
			>
				{artifact.key ?? "None"}
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Type
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 text-foreground"
			>
				{artifact.type ?? "None"}
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Created
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 text-foreground"
			>
				{createdDate ?? "None"}
			</Typography>
		</div>
	);
};
