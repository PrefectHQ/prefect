import { useSuspenseQuery } from "@tanstack/react-query";
import { LayoutGrid, Rows3 } from "lucide-react";
import { useState } from "react";
import { buildListArtifactsQuery } from "@/api/artifacts";
import type { FlowRun } from "@/api/flow-runs";
import { ArtifactCard } from "@/components/artifacts/artifact-card";
import { Card, CardContent } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/utils";

type FlowRunArtifactsProps = {
	flowRun: FlowRun;
};

export const FlowRunArtifacts = ({ flowRun }: FlowRunArtifactsProps) => {
	const [view, setView] = useState<"grid" | "list">("grid");
	const { data: artifacts } = useSuspenseQuery(
		buildListArtifactsQuery({
			artifacts: {
				operator: "and_",
				flow_run_id: {
					any_: [flowRun.id],
				},
				type: {
					not_any_: ["result"],
				},
			},
			sort: "ID_DESC",
			offset: 0,
		}),
	);
	if (artifacts.length === 0) {
		return (
			<Card>
				<CardContent className="text-center">
					<p>
						This flow run did not produce any artifacts; for more information on
						creating artifacts, see the{" "}
						<a
							href="https://docs.prefect.io/v3/develop/artifacts"
							target="_blank"
							rel="noopener noreferrer"
							className="text-blue-500"
						>
							documentation
						</a>
						.
					</p>
				</CardContent>
			</Card>
		);
	}

	return (
		<div className="flex flex-col gap-4">
			<div className="flex justify-end">
				<ToggleGroup
					type="single"
					variant="outline"
					value={view}
					onValueChange={(value) => setView(value as "grid" | "list")}
				>
					<ToggleGroupItem value="grid" aria-label="Grid view">
						<LayoutGrid className="w-4 h-4" />
					</ToggleGroupItem>
					<ToggleGroupItem value="list" aria-label="List view">
						<Rows3 className="w-4 h-4" />
					</ToggleGroupItem>
				</ToggleGroup>
			</div>
			<div
				className={cn(
					"grid",
					view === "grid"
						? "grid-cols-1 lg:grid-cols-2 xl:grid-cols-3"
						: "grid-cols-1",
					"gap-4",
				)}
				data-testid="flow-run-artifacts-grid"
			>
				{artifacts.map((artifact) => (
					<ArtifactCard
						key={artifact.id}
						artifact={artifact}
						compact={view === "list"}
					/>
				))}
			</div>
		</div>
	);
};
