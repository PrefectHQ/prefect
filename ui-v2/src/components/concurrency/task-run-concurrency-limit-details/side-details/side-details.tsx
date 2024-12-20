import { TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import { format, parseISO } from "date-fns";
import React from "react";

type Props = {
	data: TaskRunConcurrencyLimit;
};

export const SideDetails = ({ data }: Props) => {
	return (
		<div className="flex flex-col gap-4">
			<dt className="text-muted-foreground">Tag</dt>
			<dd className="text-sm font-medium leading-none">{data.tag}</dd>
			<hr />
			<dl className="flex flex-col gap-2">
				{getKeyValueList(data).map((d) => (
					<React.Fragment key={d.label}>
						<dt className="text-muted-foreground">{d.label}</dt>
						<dd className="text-sm font-medium leading-none">{d.value}</dd>
					</React.Fragment>
				))}
			</dl>
		</div>
	);
};

const getKeyValueList = (data: TaskRunConcurrencyLimit) =>
	[
		{ label: "Concurrency Limit Count", value: data.concurrency_limit },
		{
			label: "Concurrency Limit Active Task Run",
			value: data.active_slots?.length ?? "Unknown",
		},
		{
			label: "Concurrency Limit ID",
			value: data.id ?? "Unknown",
		},
		{
			label: "Created",
			value: data.created
				? format(parseISO(data.created), "yyyy/MM/dd pp")
				: "N/A",
		},
		{
			label: "Updated",
			value: data.updated
				? format(parseISO(data.updated), "yyyy/MM/dd pp")
				: "N/A",
		},
	] as const;
