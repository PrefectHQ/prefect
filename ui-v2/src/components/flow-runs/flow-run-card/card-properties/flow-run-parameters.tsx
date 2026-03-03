import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icons";
import { LazyJsonInput as JsonInput } from "@/components/ui/json-input-lazy";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { pluralize } from "@/utils";

type FlowRunParametersProps = { flowRun: FlowRunCardData };

export const FlowRunParameters = ({ flowRun }: FlowRunParametersProps) => {
	return (
		<div className="flex items-center">
			<Icon id="SlidersVertical" className="size-4" />
			<ParametersDialog flowRun={flowRun} />
		</div>
	);
};

const ParametersDialog = ({ flowRun }: FlowRunParametersProps) => {
	const parameters = flowRun.parameters ?? {};
	const numParameters = Object.keys(parameters).length;
	return (
		<Dialog>
			<Tooltip>
				<TooltipTrigger asChild>
					<span tabIndex={numParameters < 1 ? 0 : -1} className="inline-flex">
						<DialogTrigger asChild>
							<Button variant="link" size="sm" disabled={numParameters < 1}>
								{numParameters} {pluralize(numParameters, "Parameter")}
							</Button>
						</DialogTrigger>
					</span>
				</TooltipTrigger>
				{numParameters < 1 && (
					<TooltipContent>
						No parameters defined for this flow run
					</TooltipContent>
				)}
			</Tooltip>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>
						Flow run parameters for {flowRun.name ?? "Flow run"}
					</DialogTitle>
				</DialogHeader>
				<JsonInput value={JSON.stringify(parameters, null, 2)} disabled />
			</DialogContent>
		</Dialog>
	);
};
