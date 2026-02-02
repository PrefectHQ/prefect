import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense } from "react";
import { buildGetArtifactQuery } from "@/api/artifacts";
import { FormattedDate } from "@/components/ui/formatted-date/formatted-date";
import { KeyValue } from "@/components/ui/key-value";
import {
	Sheet,
	SheetContent,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

type FlowRunGraphArtifactDrawerProps = {
	artifactId: string | null;
	onClose: () => void;
};

export function FlowRunGraphArtifactDrawer({
	artifactId,
	onClose,
}: FlowRunGraphArtifactDrawerProps) {
	return (
		<Sheet
			open={artifactId !== null}
			onOpenChange={(open) => !open && onClose()}
		>
			<SheetContent>
				<SheetHeader>
					<SheetTitle>Artifact Details</SheetTitle>
				</SheetHeader>
				{artifactId && (
					<Suspense fallback={<ArtifactContentSkeleton />}>
						<ArtifactContent artifactId={artifactId} />
					</Suspense>
				)}
			</SheetContent>
		</Sheet>
	);
}

function ArtifactContentSkeleton() {
	return (
		<div className="space-y-4 p-4">
			<Skeleton className="h-6 w-32" />
			<Skeleton className="h-4 w-24" />
			<Skeleton className="h-4 w-48" />
			<Skeleton className="h-32 w-full" />
		</div>
	);
}

function ArtifactContent({ artifactId }: { artifactId: string }) {
	const { data: artifact } = useSuspenseQuery(
		buildGetArtifactQuery(artifactId),
	);

	return (
		<div className="space-y-4 p-4">
			<KeyValue
				label="Key"
				value={
					<p className="text-sm font-medium">{artifact.key ?? "Unnamed"}</p>
				}
			/>
			{artifact.type && (
				<KeyValue
					label="Type"
					value={<p className="text-sm uppercase">{artifact.type}</p>}
				/>
			)}
			{artifact.description && (
				<KeyValue
					label="Description"
					value={<p className="text-sm">{artifact.description}</p>}
				/>
			)}
			{artifact.created && (
				<KeyValue
					label="Created"
					value={<FormattedDate date={artifact.created} />}
				/>
			)}
			{artifact.data !== undefined && artifact.data !== null && (
				<div className="space-y-2">
					<p className="text-sm text-muted-foreground">Data</p>
					<pre className="bg-muted p-3 rounded-md text-sm overflow-auto max-h-64">
						{typeof artifact.data === "string"
							? artifact.data
							: JSON.stringify(artifact.data, null, 2)}
					</pre>
				</div>
			)}
		</div>
	);
}
