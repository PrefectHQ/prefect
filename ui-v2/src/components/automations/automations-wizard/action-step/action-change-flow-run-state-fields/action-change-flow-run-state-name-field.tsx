import { ActionsSchema } from "@/components/automations/automations-wizard/action-step/action-type-schemas";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useFormContext, useWatch } from "react-hook-form";
import { FLOW_STATES, FlowStates } from "./flow-states";

export const ActionChangeFlowRunStateNameField = () => {
	const form = useFormContext();
	const stateField = useWatch<ActionsSchema>({ name: "state" }) as FlowStates;
	return (
		<FormField
			control={form.control}
			name="name"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Name</FormLabel>
					<FormControl>
						<Input
							type="text"
							{...field}
							placeholder={FLOW_STATES[stateField]}
						/>
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};
