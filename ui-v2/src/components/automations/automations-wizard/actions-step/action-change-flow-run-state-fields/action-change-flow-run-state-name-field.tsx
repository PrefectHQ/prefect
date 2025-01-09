import { type ActionsSchema } from "@/components/automations/automations-wizard/actions-step/action-type-schemas";
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

type ActionChangeFlowRunStateNameFieldProps = {
	index: number;
};

export const ActionChangeFlowRunStateNameField = ({
	index,
}: ActionChangeFlowRunStateNameFieldProps) => {
	const form = useFormContext<ActionsSchema>();
	const stateField = form.watch(`actions.${index}.state`);
	return (
		<FormField
			control={form.control}
			name={`actions.${index}.name`}
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
