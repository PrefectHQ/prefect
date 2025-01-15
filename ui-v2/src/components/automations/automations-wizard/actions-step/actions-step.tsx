import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { useFieldArray, useFormContext } from "react-hook-form";
import { ActionStep } from "./action-step";

export const ActionsStep = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const { fields, append, remove } = useFieldArray({
		control: form.control,
		name: "actions",
		shouldUnregister: false,
		rules: { minLength: 1 },
	});

	return (
		<div>
			{fields.map(({ id }, index) => (
				<ActionStep key={id} index={index} onRemove={() => remove(index)} />
			))}
			<Button
				type="button"
				variant="outline"
				onClick={() => append({ type: "cancel-flow-run" })}
			>
				<Icon id="Plus" className="mr-2 h-4 w-4" /> Add Action
			</Button>
		</div>
	);
};
