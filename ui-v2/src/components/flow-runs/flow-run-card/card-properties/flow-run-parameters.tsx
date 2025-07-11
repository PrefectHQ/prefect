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
import { JsonInput } from "@/components/ui/json-input";
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
			<DialogTrigger asChild>
				<Button variant="link" size="sm" disabled={numParameters < 1}>
					{numParameters} {pluralize(numParameters, "Parameter")}
				</Button>
			</DialogTrigger>
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
