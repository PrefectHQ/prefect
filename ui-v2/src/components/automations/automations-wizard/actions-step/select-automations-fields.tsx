import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { useFormContext } from "react-hook-form";
import { type Automation, buildListAutomationsQuery } from "@/api/automations";
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
import { LoadingSelectState } from "./loading-select-state";

const INFER_OPTION = {
	value: UNASSIGNED,
	name: "Infer Automation",
} as const;

type SelectAutomationsFieldsProps = {
	action: "Pause" | "Resume";
	index: number;
};

const getButtonLabel = (
	data: Array<Automation> | undefined,
	fieldValue: string | null,
) => {
	if (fieldValue === INFER_OPTION.value) {
		return INFER_OPTION.name;
	}
	const automation = data?.find((automation) => automation.id === fieldValue);
	if (automation) {
		return automation.name;
	}
	return undefined;
};

export const SelectAutomationsFields = ({
	action,
	index,
}: SelectAutomationsFieldsProps) => {
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

	const isInferredOptionFiltered = INFER_OPTION.name
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
												selected={field.value === INFER_OPTION.value}
												onSelect={(value) => {
													field.onChange(value);
													setSearch("");
												}}
												value={INFER_OPTION.value}
											>
												{INFER_OPTION.name}
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
											<LoadingSelectState />
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
