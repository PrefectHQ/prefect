import { Artifact } from "@/api/artifacts";
import { formatDate } from "@/utils/date";
import { Link } from "@tanstack/react-router";
import { useMemo } from "react";
import Markdown from "react-markdown";
import { Card } from "../ui/card";
import { Typography } from "../ui/typography";

export type ArtifactsCardProps = {
	artifact: Artifact;
};

export const ArtifactCard = ({ artifact }: ArtifactsCardProps) => {
	const date = useMemo(() => {
		const date = new Date(artifact.updated ?? "");
		return formatDate(date, "dateTime");
	}, [artifact.updated]);
	return (
		<Link to={`/artifacts/key/$key`} params={{ key: artifact.key ?? "" }}>
			<Card className="p-4 m-2 hover:shadow-lg hover:border-blue-700">
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
					<div className="text-muted-foreground overflow-hidden truncate">
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
		</Link>
	);
};
