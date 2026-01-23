import type { ArtifactsSelection } from "@prefecthq/graphs";
import { useQuery } from "@tanstack/react-query";
import { buildListArtifactsQuery } from "@/api/artifacts";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import {
	Popover,
	PopoverAnchor,
	PopoverContent,
} from "@/components/ui/popover";
import { Typography } from "@/components/ui/typography";

type FlowRunGraphArtifactsPopoverProps = {
	selection: ArtifactsSelection;
	onClose: () => void;
	onViewArtifact: (artifactId: string) => void;
};

export function FlowRunGraphArtifactsPopover({
	selection,
	onClose,
	onViewArtifact,
}: FlowRunGraphArtifactsPopoverProps) {
	const { data: artifacts, isLoading } = useQuery(
		buildListArtifactsQuery({
			artifacts: {
				operator: "and_",
				id: { any_: selection.ids },
			},
			sort: "CREATED_DESC",
			offset: 0,
		}),
	);

	const position = selection.position;
	if (!position) {
		return null;
	}

	const anchorStyle = {
		position: "absolute" as const,
		left: `${position.x + position.width / 2}px`,
		top: `${position.y + position.height}px`,
	};

	return (
		<Popover open onOpenChange={(open) => !open && onClose()}>
			<PopoverAnchor style={anchorStyle} />
			<PopoverContent align="center" side="bottom" className="w-72">
				<div className="flex items-center justify-between mb-3">
					<Typography variant="bodySmall" className="font-semibold">
						Artifacts
					</Typography>
					<Button
						variant="ghost"
						size="icon"
						onClick={onClose}
						aria-label="Close popover"
					>
						<Icon id="X" className="size-4" />
					</Button>
				</div>
				{isLoading ? (
					<div className="flex items-center justify-center py-4">
						<Icon id="Loader2" className="size-4 animate-spin" />
					</div>
				) : (
					<div className="space-y-2 max-h-64 overflow-y-auto">
						{artifacts
							?.filter((artifact) => artifact.id !== undefined)
							.map((artifact) => (
								<div
									key={artifact.id}
									className="flex items-center justify-between gap-2 p-2 rounded-md border bg-muted/50"
								>
									<div className="flex flex-col min-w-0 flex-1">
										<Typography
											variant="bodySmall"
											className="font-medium truncate"
										>
											{artifact.key ?? "Unnamed"}
										</Typography>
										{artifact.type && (
											<Typography
												variant="xsmall"
												className="text-muted-foreground uppercase"
											>
												{artifact.type}
											</Typography>
										)}
									</div>
									<Button
										variant="outline"
										size="sm"
										onClick={() => onViewArtifact(artifact.id as string)}
									>
										View
									</Button>
								</div>
							))}
					</div>
				)}
			</PopoverContent>
		</Popover>
	);
}
