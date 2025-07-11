import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { useFormContext } from "react-hook-form";
import { buildFilterWorkPoolsQuery, type WorkPool } from "@/api/work-pools";
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
	name: "Infer Work Pool" as const,
} as const;

type SelectWorkPoolFieldsProps = {
	action: "Pause" | "Resume";
	index: number;
};

const getButtonLabel = (
	data: Array<WorkPool> | undefined,
	fieldValue: string | null,
) => {
	if (fieldValue === INFER_OPTION.value) {
		return INFER_OPTION.name;
	}
	const workPool = data?.find((wp) => wp.id === fieldValue);
	if (workPool) {
		return workPool.name;
	}
	return undefined;
};

export const SelectWorkPoolsFields = ({
	action,
	index,
}: SelectWorkPoolFieldsProps) => {
	const [search, setSearch] = useState("");
	const form = useFormContext<AutomationWizardSchema>();
	const { data, isSuccess } = useQuery(buildFilterWorkPoolsQuery());

	// nb: because work pools API does not have filtering _like by name, do client-side filtering
	const deferredSearch = useDeferredValue(search);
	const filteredData = useMemo(() => {
		if (!data) {
			return [];
		}
		return data.filter((workPool) =>
			workPool.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const isInferredOptionFiltered = INFER_OPTION.name
		.toLowerCase()
		.includes(deferredSearch.toLowerCase());

	return (
		<FormField
			control={form.control}
			name={`actions.${index}.work_pool_id`}
			render={({ field }) => {
				const buttonLabel = getButtonLabel(data, field.value);
				return (
					<FormItem className="flex flex-col">
						<FormLabel>Work Pool To {action}</FormLabel>
						<Combobox>
							<ComboboxTrigger
								selected={Boolean(buttonLabel)}
								aria-label={`Select Work Pool to ${action}`}
							>
								{buttonLabel ?? "Select Work Pool"}
							</ComboboxTrigger>
							<ComboboxContent>
								<ComboboxCommandInput
									value={search}
									onValueChange={setSearch}
									placeholder="Search for a work pool..."
								/>
								<ComboboxCommandEmtpy>No work pool found</ComboboxCommandEmtpy>
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
											filteredData.map((workPool) => (
												<ComboboxCommandItem
													key={workPool.id}
													selected={field.value === workPool.id}
													onSelect={(value) => {
														field.onChange(value);
														setSearch("");
													}}
													value={workPool.id}
												>
													{workPool.name}
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
