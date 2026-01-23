import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import {
	Popover,
	PopoverAnchor,
	PopoverContent,
} from "@/components/ui/popover";
import { Typography } from "@/components/ui/typography";

type Artifact = {
	id: string;
	key: string | null;
	type: string | null;
};

type FlowRunGraphArtifactsPopoverProps = {
	artifacts: Artifact[];
	position: { x: number; y: number; width: number; height: number };
	onClose: () => void;
	onViewArtifact: (artifactId: string) => void;
};

export function FlowRunGraphArtifactsPopover({
	artifacts,
	position,
	onClose,
	onViewArtifact,
}: FlowRunGraphArtifactsPopoverProps) {
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
				<div className="space-y-2 max-h-64 overflow-y-auto">
					{artifacts.map((artifact) => (
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
								onClick={() => onViewArtifact(artifact.id)}
							>
								View
							</Button>
						</div>
					))}
				</div>
			</PopoverContent>
		</Popover>
	);
}
