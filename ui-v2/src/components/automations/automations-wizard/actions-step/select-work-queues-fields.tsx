import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { useFormContext } from "react-hook-form";
import { buildFilterWorkQueuesQuery, type WorkQueue } from "@/api/work-queues";
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
	name: "Infer Work Queue" as const,
} as const;

type SelectWorkQueuesFieldsProps = {
	action: "Pause" | "Resume";
	index: number;
};

const getButtonLabel = (
	data: Array<WorkQueue> | undefined,
	fieldValue: string | null,
) => {
	if (fieldValue === INFER_OPTION.value) {
		return INFER_OPTION.name;
	}
	const workQueue = data?.find((wq) => wq.id === fieldValue);
	if (workQueue) {
		return workQueue.name;
	}
	return undefined;
};

export const SelectWorkQueuesFields = ({
	action,
	index,
}: SelectWorkQueuesFieldsProps) => {
	const [search, setSearch] = useState("");
	const form = useFormContext<AutomationWizardSchema>();
	const { data } = useQuery(buildFilterWorkQueuesQuery());

	// nb: because work queues API does not have filtering _like by name, do client-side filtering
	const deferredSearch = useDeferredValue(search);

	// Filters data, but returns as a map of work_pool_name vs work queues
	const filteredMap = useMemo(() => {
		if (!data) {
			return undefined;
		}
		const filteredMap = new Map<string, Array<WorkQueue>>();
		const filteredWorkQueues = data.filter((workQueue) =>
			workQueue.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
		for (const wq of filteredWorkQueues) {
			const { work_pool_name } = wq;
			if (!work_pool_name) {
				throw new Error("'work_pool_name expected");
			}
			filteredMap.set(work_pool_name, [
				...(filteredMap.get(work_pool_name) ?? []),
				wq,
			]);
		}

		return filteredMap;
	}, [data, deferredSearch]);

	const isInferredOptionFiltered = INFER_OPTION.name
		.toLowerCase()
		.includes(deferredSearch.toLowerCase());

	return (
		<FormField
			control={form.control}
			name={`actions.${index}.work_queue_id`}
			render={({ field }) => {
				const buttonLabel = getButtonLabel(data, field.value);
				return (
					<FormItem className="flex flex-col">
						<FormLabel>Work Queue To {action}</FormLabel>
						<Combobox>
							<ComboboxTrigger
								selected={Boolean(buttonLabel)}
								aria-label={`Select Work Queue to ${action}`}
							>
								{buttonLabel ?? "Select Work Queue"}
							</ComboboxTrigger>
							<ComboboxContent>
								<ComboboxCommandInput
									value={search}
									onValueChange={setSearch}
									placeholder="Search for a work queue..."
								/>
								<ComboboxCommandEmtpy>No work queue found</ComboboxCommandEmtpy>
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
										{filteredMap ? (
											Array.from(filteredMap).map(
												([workPoolName, workQueues]) => (
													<div key={workPoolName} className="border-b">
														<ComboboxCommandItem disabled>
															{workPoolName}
														</ComboboxCommandItem>
														{workQueues.map((workQueue) => (
															<ComboboxCommandItem
																key={workQueue.id}
																selected={field.value === workQueue.id}
																onSelect={(value) => {
																	field.onChange(value);
																	setSearch("");
																}}
																value={workQueue.id}
															>
																{workQueue.name}
															</ComboboxCommandItem>
														))}
													</div>
												),
											)
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
