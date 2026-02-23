import { Link } from "@tanstack/react-router";
import { useMemo } from "react";
import type { Artifact } from "@/api/artifacts";
import { LazyMarkdown } from "@/components/ui/lazy-markdown";
import { cn } from "@/utils";
import { formatDate } from "@/utils/date";
import { Card, CardContent, CardHeader } from "../ui/card";

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
			<Card className="hover:shadow-lg hover:border-primary">
				<CardHeader>
					<p className="text-sm font-bold text-muted-foreground">
						{artifact.type?.toUpperCase()}
					</p>
				</CardHeader>
				<CardContent>
					<div
						className={cn(
							"flex",
							compact ? "flex-row justify-between" : "flex-col",
						)}
					>
						{compact ? (
							<h4 className="text-xl font-semibold tracking-tight font-bold">
								{artifact.key}
							</h4>
						) : (
							<h3 className="text-2xl font-semibold tracking-tight font-bold">
								{artifact.key}
							</h3>
						)}
						<div
							className={cn(
								"flex mt-2",
								compact ? "flex-col-reverse items-end" : "justify-between",
							)}
						>
							{compact ? (
								<p className="text-sm font-mono">{createdAtDate}</p>
							) : (
								<p className="text-xs font-mono">{createdAtDate}</p>
							)}
							<p className="text-sm text-muted-foreground">Created</p>
						</div>
					</div>
					<hr className="my-2" />
					{artifact.description ? (
						<div className="text-muted-foreground overflow-hidden truncate">
							<LazyMarkdown>{artifact.description ?? ""}</LazyMarkdown>
						</div>
					) : (
						<p className="text-sm text-muted-foreground italic">
							No description
						</p>
					)}
				</CardContent>
			</Card>
		</Link>
	);
};
