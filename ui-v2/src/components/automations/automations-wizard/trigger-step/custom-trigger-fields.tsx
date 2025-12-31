import { useFormContext, useWatch } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { DurationInput } from "./duration-input";
import { EventsCombobox } from "./events-combobox";
import { PostureSelect } from "./posture-select";
import { ResourceCombobox } from "./resource-combobox";

function toPluralString(word: string, count: number): string {
	return count === 1 ? word : `${word}s`;
}

export const CustomTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });
	const threshold = useWatch<AutomationWizardSchema>({
		name: "trigger.threshold",
	});

	return (
		<div className="space-y-4">
			<PostureSelect />

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
									onEventsChange={(newEvents) => {
										field.onChange(newEvents.length > 0 ? newEvents : []);
									}}
									emptyMessage="All events"
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
					const match = field.value ?? {};
					const resourceIds = match["prefect.resource.id"] ?? [];
					const selectedResources = Array.isArray(resourceIds)
						? resourceIds
						: [resourceIds];
					return (
						<FormItem>
							<FormLabel>From the following resources</FormLabel>
							<FormControl>
								<ResourceCombobox
									selectedResources={selectedResources}
									onResourcesChange={(newResources) => {
										if (newResources.length === 0) {
											const { "prefect.resource.id": _resourceId, ...rest } =
												match;
											void _resourceId;
											field.onChange(Object.keys(rest).length > 0 ? rest : {});
										} else {
											field.onChange({
												...match,
												"prefect.resource.id": newResources,
											});
										}
									}}
									emptyMessage="All resources"
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					);
				}}
			/>

			<div className="flex items-center gap-2">
				<FormField
					control={form.control}
					name="trigger.threshold"
					render={({ field }) => (
						<FormItem className="w-24">
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
				<span className="text-sm text-muted-foreground shrink-0">
					{toPluralString("time", threshold ?? 1)} within
				</span>
				<FormField
					control={form.control}
					name="trigger.within"
					render={({ field }) => (
						<FormItem className="flex-1">
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

			<Accordion type="single" collapsible className="w-full">
				<AccordionItem value="evaluation-options">
					<AccordionTrigger>Evaluation Options</AccordionTrigger>
					<AccordionContent>
						<div className="space-y-4">
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
													onEventsChange={(newEvents) => {
														field.onChange(
															newEvents.length > 0 ? newEvents : [],
														);
													}}
													emptyMessage="Any event"
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
									const matchRelated = field.value ?? {};
									const resourceIds = matchRelated["prefect.resource.id"] ?? [];
									const selectedResources = Array.isArray(resourceIds)
										? resourceIds
										: [resourceIds];
									return (
										<FormItem>
											<FormLabel>Filter for events related to</FormLabel>
											<FormControl>
												<ResourceCombobox
													selectedResources={selectedResources}
													onResourcesChange={(newResources) => {
														if (newResources.length === 0) {
															const {
																"prefect.resource.id": _resourceId,
																...rest
															} = matchRelated;
															void _resourceId;
															field.onChange(
																Object.keys(rest).length > 0 ? rest : {},
															);
														} else {
															field.onChange({
																...matchRelated,
																"prefect.resource.id": newResources,
															});
														}
													}}
													emptyMessage="All resources"
												/>
											</FormControl>
											<FormMessage />
										</FormItem>
									);
								}}
							/>
						</div>
					</AccordionContent>
				</AccordionItem>
			</Accordion>
		</div>
	);
};
