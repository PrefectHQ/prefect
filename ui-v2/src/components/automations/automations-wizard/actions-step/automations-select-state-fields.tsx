import { Automation, buildListAutomationsQuery } from "@/api/automations";
import {
	type AutomationWizardSchema,
	UNASSIGNED,
} from "@/components/automations/automations-wizard/automation-schema";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "@/components/ui/combobox";

import {
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { useFormContext } from "react-hook-form";

const INFER_AUTOMATION = {
	value: UNASSIGNED,
	name: "Infer Automation" as const,
} as const;

const NUM_SKELETONS = 4;

type AutomationsSelectStateFieldsProps = {
	action: "Pause" | "Resume";
	index: number;
};

const getButtonLabel = (
	data: Array<Automation> | undefined,
	fieldValue: string | null,
) => {
	if (fieldValue === INFER_AUTOMATION.value) {
		return INFER_AUTOMATION.name;
	}
	const automation = data?.find((automation) => automation.id === fieldValue);
	if (automation) {
		return automation.name;
	}
	return undefined;
};

export const AutomationsSelectStateFields = ({
	action,
	index,
}: AutomationsSelectStateFieldsProps) => {
	const [search, setSearch] = useState("");
	const form = useFormContext<AutomationWizardSchema>();
	const { data, isSuccess } = useQuery(buildListAutomationsQuery());

	// nb: because automations API does not have filtering _like by name, do client-side filtering
	const deferredSearch = useDeferredValue(search);
	const filteredData = useMemo(() => {
		if (!data) {
			return [];
		}
		return data.filter((automation) =>
			automation.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const isInferredOptionFiltered = INFER_AUTOMATION.name
		.toLowerCase()
		.includes(deferredSearch.toLowerCase());

	return (
		<FormField
			control={form.control}
			name={`actions.${index}.automation_id`}
			render={({ field }) => {
				const buttonLabel = getButtonLabel(data, field.value);
				return (
					<FormItem className="flex flex-col">
						<FormLabel>Automation To {action}</FormLabel>
						<Combobox>
							<ComboboxTrigger
								selected={Boolean(buttonLabel)}
								aria-label={`Select Automation to ${action}`}
							>
								{buttonLabel ?? "Select automation"}
							</ComboboxTrigger>
							<ComboboxContent>
								<ComboboxCommandInput
									value={search}
									onValueChange={setSearch}
									placeholder="Search for an automation..."
								/>
								<ComboboxCommandEmtpy>No automation found</ComboboxCommandEmtpy>
								<ComboboxCommandList>
									<ComboboxCommandGroup>
										{isInferredOptionFiltered && (
											<ComboboxCommandItem
												selected={field.value === INFER_AUTOMATION.value}
												onSelect={(value) => {
													field.onChange(value);
													setSearch("");
												}}
												value={INFER_AUTOMATION.value}
											>
												{INFER_AUTOMATION.name}
											</ComboboxCommandItem>
										)}
										{isSuccess ? (
											filteredData.map((automation) => (
												<ComboboxCommandItem
													key={automation.id}
													selected={field.value === automation.id}
													onSelect={(value) => {
														field.onChange(value);
														setSearch("");
													}}
													value={automation.id}
												>
													{automation.name}
												</ComboboxCommandItem>
											))
										) : (
											<AutomationLoadingState length={NUM_SKELETONS} />
										)}
									</ComboboxCommandGroup>
								</ComboboxCommandList>
							</ComboboxContent>
						</Combobox>
						<FormMessage />
					</FormItem>
				);
			}}
		/>
	);
};

const AutomationLoadingState = ({ length }: { length: number }) =>
	Array.from({ length }, (_, index) => (
		<Skeleton key={index} className="mt-2 p-4 h-2 w-full" />
	));
