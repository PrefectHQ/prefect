import { Automation, buildListAutomationsQuery } from "@/api/automations";
import {
	ActionsSchema,
	UNASSIGNED,
} from "@/components/automations/automations-wizard/actions-step/action-type-schemas";
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
	if (automation?.name) {
		return automation.name;
	}
	return undefined;
};

/** Because ShadCN only filters by `value` and not by a specific field, we need to write custom logic to filter objects by id */
const filterAutomations = (
	value: string | null,
	search: string,
	data: Array<Automation> | undefined,
) => {
	const searchTerm = search.toLowerCase();
	const automation = data?.find((automation) => automation.id === value);
	if (!automation) {
		return 0;
	}
	const automationName = automation.name.toLowerCase();
	if (automationName.includes(searchTerm)) {
		return 1;
	}
	return 0;
};

export const AutomationsSelectStateFields = ({
	action,
	index,
}: AutomationsSelectStateFieldsProps) => {
	const form = useFormContext<ActionsSchema>();
	const { data, isSuccess } = useQuery(buildListAutomationsQuery());

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
								{getButtonLabel(data, field.value) ?? "Select automation"}
							</ComboboxTrigger>
							<ComboboxContent
								filter={(value, search) =>
									filterAutomations(value, search, data)
								}
							>
								<ComboboxCommandInput placeholder="Search for an automation..." />
								<ComboboxCommandEmtpy>No automation found</ComboboxCommandEmtpy>
								<ComboboxCommandList>
									<ComboboxCommandGroup>
										<ComboboxCommandItem
											selected={field.value === INFER_AUTOMATION.value}
											onSelect={field.onChange}
											value={INFER_AUTOMATION.value}
										>
											{INFER_AUTOMATION.name}
										</ComboboxCommandItem>
										{isSuccess ? (
											data.map((automation) => (
												<ComboboxCommandItem
													key={automation.id}
													selected={field.value === automation.id}
													onSelect={field.onChange}
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
