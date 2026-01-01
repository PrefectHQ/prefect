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
import { CustomPostureSelect } from "./custom-posture-select";
import { EventResourceCombobox } from "./event-resource-combobox";
import { EventsCombobox } from "./events-combobox";

export const CustomTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });

	return (
		<div className="space-y-4">
			<div className="flex items-end gap-4">
				<CustomPostureSelect />
			</div>

			<FormField
				control={form.control}
				name="trigger.expect"
				render={({ field }) => {
					const events = field.value ?? [];
					return (
						<FormItem>
							<FormLabel>Any event matching</FormLabel>
							<FormControl>
								<EventsCombobox
									selectedEvents={events}
									onToggleEvent={(event) => {
										const newEvents = events.includes(event)
											? events.filter((e) => e !== event)
											: [...events, event];
										field.onChange(newEvents);
									}}
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
					const resourceIdsArray = Array.isArray(resourceIds)
						? resourceIds
						: [resourceIds];
					return (
						<FormItem>
							<FormLabel>From the following resources</FormLabel>
							<FormControl>
								<EventResourceCombobox
									selectedResourceIds={resourceIdsArray}
									onToggleResource={(resourceId) => {
										const newIds = resourceIdsArray.includes(resourceId)
											? resourceIdsArray.filter((id) => id !== resourceId)
											: [...resourceIdsArray, resourceId];
										if (newIds.length > 0) {
											field.onChange({ "prefect.resource.id": newIds });
										} else {
											field.onChange({});
										}
									}}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					);
				}}
			/>

			<div className="flex items-end gap-2">
				<FormField
					control={form.control}
					name="trigger.threshold"
					render={({ field }) => (
						<FormItem className="w-20">
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
				<span className="pb-2 text-sm text-muted-foreground">times within</span>
				<FormField
					control={form.control}
					name="trigger.within"
					render={({ field }) => (
						<FormItem>
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
							return (
								<FormItem>
									<FormLabel>
										Evaluate trigger only after observing an event matching
									</FormLabel>
									<FormControl>
										<EventsCombobox
											selectedEvents={events}
											onToggleEvent={(event) => {
												const newEvents = events.includes(event)
													? events.filter((e) => e !== event)
													: [...events, event];
												field.onChange(newEvents);
											}}
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
							const resourceIdsArray = Array.isArray(resourceIds)
								? resourceIds
								: [resourceIds];
							return (
								<FormItem>
									<FormLabel>Filter for events related to</FormLabel>
									<FormControl>
										<EventResourceCombobox
											selectedResourceIds={resourceIdsArray}
											onToggleResource={(resourceId) => {
												const newIds = resourceIdsArray.includes(resourceId)
													? resourceIdsArray.filter((id) => id !== resourceId)
													: [...resourceIdsArray, resourceId];
												if (newIds.length > 0) {
													field.onChange({ "prefect.resource.id": newIds });
												} else {
													field.onChange({});
												}
											}}
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
