import { useFormContext, useWatch } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { PostureSelect } from "./posture-select";

export const CustomTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });

	return (
		<div className="space-y-4">
			<div className="flex items-end gap-4">
				<PostureSelect />
			</div>

			<FormField
				control={form.control}
				name="trigger.expect"
				render={({ field }) => {
					const events = field.value ?? [];
					const textValue = events.join("\n");
					return (
						<FormItem>
							<FormLabel>Expected Events (one per line)</FormLabel>
							<FormControl>
								<Textarea
									placeholder="prefect.flow-run.Completed"
									value={textValue}
									onChange={(e) => {
										const lines = e.target.value
											.split("\n")
											.filter((line) => line.trim() !== "");
										field.onChange(lines.length > 0 ? lines : undefined);
									}}
									rows={4}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					);
				}}
			/>

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
