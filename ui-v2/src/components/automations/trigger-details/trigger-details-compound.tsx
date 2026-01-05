import { Typography } from "@/components/ui/typography";
import type { CompoundTrigger } from "./trigger-utils";

type TriggerDetailsCompoundProps = {
	trigger: CompoundTrigger;
};

export const TriggerDetailsCompound = ({
	trigger,
}: TriggerDetailsCompoundProps) => {
	const triggerCount = trigger.triggers?.length ?? 0;
	const requireValue = trigger.require;

	let requireLabel: string;
	if (requireValue === "all") {
		requireLabel = "all";
	} else if (requireValue === "any") {
		requireLabel = "any";
	} else if (typeof requireValue === "number") {
		requireLabel = `at least ${requireValue}`;
	} else {
		requireLabel = "all";
	}

	return (
		<div className="flex flex-wrap gap-1 items-center">
			<Typography variant="bodySmall">
				A compound trigger requiring {requireLabel} of {triggerCount} nested{" "}
				{triggerCount === 1 ? "trigger" : "triggers"} to fire
			</Typography>
		</div>
	);
};
