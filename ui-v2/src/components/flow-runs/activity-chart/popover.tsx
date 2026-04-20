import { Link } from "@tanstack/react-router";
import humanizeDuration from "humanize-duration";
import type { FlowRun } from "@/api/flow-runs";
import { Icon } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";

export type PopoverProps = {
	name: string;
	flowRun: FlowRun | null;
};

export const Popover = ({ name, flowRun }: PopoverProps) => {
	return (
		<div
			data-testid="popover"
			className="bg-background border rounded-lg p-4 flex flex-col gap-2"
		>
			<p className="text-base text-foreground">
				{name} {">"}{" "}
				<Link
					to="/runs/flow-run/$id"
					params={{ id: flowRun?.id ?? "" }}
					className="text-link hover:text-link-hover hover:underline"
				>
					{flowRun?.name}
				</Link>
			</p>
			<div>
				<StateBadge type={flowRun?.state_type ?? "CANCELLED"} />
			</div>
			<hr />
			<div className="flex flex-col justify-between">
				<p className="text-sm text-foreground flex items-center">
					<Icon id="Clock" width="16" className="mr-2" />{" "}
					{humanizeDuration(
						Math.ceil((flowRun?.estimated_run_time ?? 0) * 1000),
					)}
				</p>
				<p className="text-sm text-foreground flex items-center">
					<Icon id="Calendar" width="16" className="mr-2" />{" "}
					{new Date(
						flowRun?.start_time ?? flowRun?.expected_start_time ?? "",
					).toLocaleString()}
				</p>
			</div>
		</div>
	);
};
