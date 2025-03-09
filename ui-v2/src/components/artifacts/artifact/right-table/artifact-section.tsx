import { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Typography } from "@/components/ui/typography";
import { formatDate } from "@/utils/date";
import { useMemo } from "react";

type ArtifactSectionProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactSection = ({ artifact }: ArtifactSectionProps) => {
	const date = useMemo(() => {
		const date = new Date(artifact.created ?? "");
		return formatDate(date, "dateTime");
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
				className={`${artifact.key ? "bg-gray-100 p-1 mx-1 mt-1 rounded" : ""} inline`}
			>
				{artifact.key ?? " "}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Type
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className={`${artifact.type ? "bg-gray-100 p-1 mx-1 mt-1 rounded" : ""} inline`}
			>
				{artifact.type ?? " "}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Created
			</Typography>
			<Typography variant="bodySmall" fontFamily="mono" className="mt-1">
				{date}
			</Typography>
		</div>
	);
};
