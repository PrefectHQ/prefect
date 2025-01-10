import { ActionsSchema } from "@/components/automations/automations-wizard/action-step/action-type-schemas";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useFormContext } from "react-hook-form";
import { FLOW_STATES } from "./flow-states";

export const ActionChangeFlowRunStateNameField = () => {
	const form = useFormContext<ActionsSchema>();
	const stateField = form.watch("state");
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
							value={field.value ?? ""}
							placeholder={FLOW_STATES[stateField]}
						/>
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};
