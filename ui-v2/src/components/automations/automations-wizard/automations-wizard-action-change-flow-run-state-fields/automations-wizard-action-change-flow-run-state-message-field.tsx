import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { useFormContext } from "react-hook-form";

export const AutomationsWizardActionChangeFlowRunStateMessageField = () => {
	const form = useFormContext();
	return (
		<FormField
			control={form.control}
			name="message"
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
