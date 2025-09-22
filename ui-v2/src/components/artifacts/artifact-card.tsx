import { Link } from "@tanstack/react-router";
import { useMemo } from "react";
import Markdown from "react-markdown";
import type { Artifact } from "@/api/artifacts";
import { cn } from "@/utils";
import { formatDate } from "@/utils/date";
import { Card, CardContent, CardHeader } from "../ui/card";
import { Typography } from "../ui/typography";

export type ArtifactsCardProps = {
	artifact: Artifact;
	compact?: boolean;
};

export const ArtifactCard = ({
	artifact,
	compact = false,
}: ArtifactsCardProps) => {
	const createdAtDate = useMemo(() => {
		return formatDate(new Date(artifact.created ?? ""), "dateTime");
	}, [artifact.created]);
	return (
		<Link to="/artifacts/key/$key" params={{ key: artifact.key ?? "" }}>
			<Card className="hover:shadow-lg hover:border-blue-700">
				<CardHeader>
					<Typography
						variant="bodySmall"
						className="font-bold text-muted-foreground"
					>
						{artifact.type?.toUpperCase()}
					</Typography>
				</CardHeader>
				<CardContent>
					<div
						className={cn(
							"flex",
							compact ? "flex-row justify-between" : "flex-col",
						)}
					>
						<Typography variant={compact ? "h4" : "h3"} className="font-bold">
							{artifact.key}
						</Typography>
						<div
							className={cn(
								"flex mt-2",
								compact ? "flex-col-reverse items-end" : "justify-between",
							)}
						>
							<Typography
								variant={compact ? "bodySmall" : "xsmall"}
								className=""
								fontFamily="mono"
							>
								{createdAtDate}
							</Typography>
							<Typography variant="bodySmall" className="text-muted-foreground">
								Created
							</Typography>
						</div>
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
				</CardContent>
			</Card>
		</Link>
	);
};
