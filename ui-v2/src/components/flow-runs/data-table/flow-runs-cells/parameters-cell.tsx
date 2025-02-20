import {
	type FlowRunWithDeploymentAndFlow,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { Button } from "@/components/ui/button";
import { DialogHeader } from "@/components/ui/dialog";
import {
	Dialog,
	DialogContent,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icons";
import { JsonInput } from "@/components/ui/json-input";
import { pluralize } from "@/utils";
import type { CellContext } from "@tanstack/react-table";

type ParametersCellProps = CellContext<
	FlowRunWithFlow | FlowRunWithDeploymentAndFlow,
	Record<string, unknown> | undefined
>;

export const ParametersCell = (props: ParametersCellProps) => {
	const flowRunName = props.row.original.name;
	const parameters = props.getValue() ?? {};
	return (
		<div className="flex items-center">
			<Icon id="SlidersVertical" className="h-4 w-4" />
			<ParametersDialog flowRunName={flowRunName} parameters={parameters} />
		</div>
	);
};

type ParametersDialogProps = {
	flowRunName: string | undefined;
	parameters: Record<string, unknown>;
};

export const ParametersDialog = ({
	flowRunName,
	parameters,
}: ParametersDialogProps) => {
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
						Flow run parameters for {flowRunName ?? "Flow run"}
					</DialogTitle>
				</DialogHeader>
				<JsonInput value={JSON.stringify(parameters, null, 2)} disabled />
			</DialogContent>
		</Dialog>
	);
};
