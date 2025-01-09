import { type ActionsSchema } from "@/components/automations/automations-wizard/actions-step/action-type-schemas";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { useFormContext } from "react-hook-form";

type ActionChangeFlowRunStateMessageFieldProps = {
	index: number;
};

export const ActionChangeFlowRunStateMessageField = ({
	index,
}: ActionChangeFlowRunStateMessageFieldProps) => {
	const form = useFormContext<ActionsSchema>();
	return (
		<FormField
			control={form.control}
			name={`actions.${index}.message`}
			render={({ field }) => (
				<FormItem>
					<FormLabel>Message</FormLabel>
					<FormControl>
						<Textarea
							{...field}
							placeholder="State changed by Automation <id>"
						/>
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};
