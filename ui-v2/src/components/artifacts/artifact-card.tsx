import { Artifact } from "@/api/artifacts";
import { formatDate } from "@/utils/date";
import { useMemo } from "react";
import Markdown from "react-markdown";
import { Card } from "../ui/card";
import { Typography } from "../ui/typography";

interface ArtifactsCardProps {
	artifact: Artifact;
}

export const ArtifactCard = ({ artifact }: ArtifactsCardProps) => {
	const date = useMemo(() => {
		const date = new Date(artifact.updated ?? "");
		return formatDate(date, "dateTime");
	}, [artifact.updated]);
	return (
		<Card className="p-4 m-2">
			<Typography
				variant="bodySmall"
				className="font-bold text-muted-foreground"
			>
				{artifact.type?.toUpperCase()}
			</Typography>
			<Typography variant="h3" className="font-bold">
				{artifact.key}
			</Typography>
			<div className="flex justify-between mt-2">
				<Typography variant="bodySmall" className="" fontFamily="mono">
					{date}
				</Typography>
				<Typography variant="bodySmall" className="text-muted-foreground">
					Last Updated
				</Typography>
			</div>
			<hr className="my-2" />
			{artifact.description ? (
				<div className="text-muted-foreground">
					<Markdown>{artifact.description ?? ""}</Markdown>
				</div>
			) : (
				<Typography
					variant="bodySmall"
					className="text-muted-foreground italic"
				>
					No description
				</Typography>
			)}
		</Card>
	);
};
