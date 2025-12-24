import { useFormContext, useWatch } from "react-hook-form";
import type { components } from "@/api/prefect";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { PostureSelect } from "./posture-select";
import { StateMultiSelect } from "./state-multi-select";

type StateType = components["schemas"]["StateType"];

export const FlowRunStateTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });

	// Determine which field to use based on posture
	// Reactive: use "expect" (states to enter)
	// Proactive: use "after" (states to stay in)
	const stateFieldName =
		posture === "Proactive" ? "trigger.after" : "trigger.expect";
	const stateFieldLabel =
		posture === "Proactive" ? "States to stay in" : "States to enter";

	return (
		<div className="space-y-4">
			<div className="flex items-end gap-4">
				<PostureSelect />
				<FormField
					control={form.control}
					name={stateFieldName}
					render={({ field }) => {
						const selectedStates = (field.value ?? []) as StateType[];
						return (
							<FormItem className="flex-1">
								<FormLabel>{stateFieldLabel}</FormLabel>
								<FormControl>
									<StateMultiSelect
										selectedStates={selectedStates}
										onToggleState={(state) => {
											const currentStates = selectedStates;
											if (currentStates.includes(state)) {
												field.onChange(
													currentStates.filter((s) => s !== state),
												);
											} else {
												field.onChange([...currentStates, state]);
											}
										}}
										emptyMessage="Any state"
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						);
					}}
				/>
			</div>

			<div className="flex gap-4">
				<FormField
					control={form.control}
					name="trigger.threshold"
					render={({ field }) => (
						<FormItem className="w-32">
							<FormLabel>Threshold</FormLabel>
							<FormControl>
								<Input
									type="number"
									min={1}
									{...field}
									onChange={(e) => field.onChange(Number(e.target.value))}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				{posture === "Proactive" && (
					<FormField
						control={form.control}
						name="trigger.within"
						render={({ field }) => (
							<FormItem className="w-32">
								<FormLabel>Within (seconds)</FormLabel>
								<FormControl>
									<Input
										type="number"
										min={0}
										{...field}
										onChange={(e) => field.onChange(Number(e.target.value))}
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>
				)}
			</div>
		</div>
	);
};
