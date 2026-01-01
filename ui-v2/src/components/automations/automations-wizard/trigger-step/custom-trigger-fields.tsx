import { ChevronRight } from "lucide-react";
import { useFormContext, useWatch } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { DurationInput } from "@/components/ui/duration-input";
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

			<FormField
				control={form.control}
				name="trigger.match"
				render={({ field }) => {
					const resourceIds =
						(field.value?.["prefect.resource.id"] as string[] | undefined) ??
						[];
					const textValue = Array.isArray(resourceIds)
						? resourceIds.join("\n")
						: resourceIds;
					return (
						<FormItem>
							<FormLabel>From the following resources (one per line)</FormLabel>
							<FormControl>
								<Textarea
									placeholder="prefect.flow-run.*"
									value={textValue}
									onChange={(e) => {
										const lines = e.target.value
											.split("\n")
											.filter((line) => line.trim() !== "");
										if (lines.length > 0) {
											field.onChange({ "prefect.resource.id": lines });
										} else {
											field.onChange({});
										}
									}}
									rows={3}
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

				<FormField
					control={form.control}
					name="trigger.within"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Within</FormLabel>
							<FormControl>
								<DurationInput
									value={field.value ?? 0}
									onChange={field.onChange}
									min={posture === "Proactive" ? 10 : 0}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
			</div>

			<Collapsible>
				<CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium">
					<ChevronRight className="h-4 w-4 transition-transform data-[state=open]:rotate-90" />
					Evaluation Options
				</CollapsibleTrigger>
				<CollapsibleContent className="mt-4 space-y-4 pl-6">
					<FormField
						control={form.control}
						name="trigger.after"
						render={({ field }) => {
							const events = field.value ?? [];
							const textValue = events.join("\n");
							return (
								<FormItem>
									<FormLabel>
										Evaluate trigger only after observing an event matching
									</FormLabel>
									<FormControl>
										<Textarea
											placeholder="prefect.flow-run.Pending"
											value={textValue}
											onChange={(e) => {
												const lines = e.target.value
													.split("\n")
													.filter((line) => line.trim() !== "");
												field.onChange(lines.length > 0 ? lines : []);
											}}
											rows={3}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							);
						}}
					/>

					<FormField
						control={form.control}
						name="trigger.match_related"
						render={({ field }) => {
							const resourceIds =
								(field.value?.["prefect.resource.id"] as
									| string[]
									| undefined) ?? [];
							const textValue = Array.isArray(resourceIds)
								? resourceIds.join("\n")
								: resourceIds;
							return (
								<FormItem>
									<FormLabel>Filter for events related to</FormLabel>
									<FormControl>
										<Textarea
											placeholder="prefect.flow.*"
											value={textValue}
											onChange={(e) => {
												const lines = e.target.value
													.split("\n")
													.filter((line) => line.trim() !== "");
												if (lines.length > 0) {
													field.onChange({ "prefect.resource.id": lines });
												} else {
													field.onChange({});
												}
											}}
											rows={3}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							);
						}}
					/>
				</CollapsibleContent>
			</Collapsible>
		</div>
	);
};
