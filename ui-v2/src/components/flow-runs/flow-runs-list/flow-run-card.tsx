import { components } from "@/api/prefect";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Typography } from "@/components/ui/typography";
import { cva } from "class-variance-authority";
import type { FlowRunRow } from "./types";

type FlowRunCardProps =
	| {
			flowRun: FlowRunRow;
	  }
	| {
			flowRun: FlowRunRow;
			checked: boolean;
			onCheckedChange: (checked: boolean) => void;
	  };

export const FlowRunCard = ({ flowRun, ...props }: FlowRunCardProps) => {
	return (
		<Card className={stateCardVariants({ state: flowRun.state?.type })}>
			<div className="flex items-center gap-2">
				{"checked" in props && "onCheckedChange" in props && (
					<Checkbox
						checked={props.checked}
						onCheckedChange={props.onCheckedChange}
					/>
				)}
				<Typography>{flowRun.name}</Typography>
			</div>
		</Card>
	);
};

const stateCardVariants = cva("flex flex-col gap-2 p-4 border-l-8", {
	variants: {
		state: {
			COMPLETED: "border-l-green-600",
			FAILED: "border-l-red-600",
			RUNNING: "border-l-blue-700",
			CANCELLED: "border-l-gray-800",
			CANCELLING: "border-l-gray-800",
			CRASHED: "border-l-orange-600",
			PAUSED: "border-l-gray-800",
			PENDING: "border-l-gray-800",
			SCHEDULED: "border-l-yellow-700",
		} satisfies Record<components["schemas"]["StateType"], string>,
	},
});
