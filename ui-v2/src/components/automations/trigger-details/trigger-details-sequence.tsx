import { Typography } from "@/components/ui/typography";
import type { SequenceTrigger } from "./trigger-utils";

type TriggerDetailsSequenceProps = {
	trigger: SequenceTrigger;
};

export const TriggerDetailsSequence = ({
	trigger,
}: TriggerDetailsSequenceProps) => {
	const triggerCount = trigger.triggers?.length ?? 0;

	return (
		<div className="flex flex-wrap gap-1 items-center">
			<Typography variant="bodySmall">
				A sequence trigger with {triggerCount} nested{" "}
				{triggerCount === 1 ? "trigger" : "triggers"} that must fire in order
			</Typography>
		</div>
	);
};
