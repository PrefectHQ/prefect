import { format, parseISO } from "date-fns";
import React from "react";
import type { TaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";
import { cn } from "@/utils";

type TaskRunConcurrencyLimitDetailsProps = {
	data: TaskRunConcurrencyLimit;
};

export const TaskRunConcurrencyLimitDetails = ({
	data,
}: TaskRunConcurrencyLimitDetailsProps) => {
	return (
		<div className="flex flex-col gap-4">
			<dl className="flex flex-col gap-2">
				<dt className="text-muted-foreground">Tag</dt>
				<dd className="text-sm font-medium leading-none">{data.tag}</dd>
			</dl>
			<hr />
			<dl className="flex flex-col gap-2">
				{getKeyValueList(data).map((d) => (
					<React.Fragment key={d.label}>
						<dt className="text-muted-foreground">{d.label}</dt>
						<dd
							className={cn(
								"text-sm font-medium leading-none",
								d.formatType === "date" && "font-mono",
							)}
						>
							{d.value}
						</dd>
					</React.Fragment>
				))}
			</dl>
		</div>
	);
};

const getKeyValueList = (data: TaskRunConcurrencyLimit) =>
	[
		{
			label: "Concurrency Limit Count",
			value: data.concurrency_limit,
			formatType: "number",
		},
		{
			label: "Concurrency Limit Active Task Run",
			value: data.active_slots?.length ?? "Unknown",
			formatType: "number",
		},
		{
			label: "Concurrency Limit ID",
			value: data.id ?? "Unknown",
			formatType: "number",
		},
		{
			label: "Created",
			value: data.created
				? format(parseISO(data.created), "yyyy/MM/dd pp")
				: "N/A",
			formatType: "date",
		},
		{
			label: "Updated",
			value: data.updated
				? format(parseISO(data.updated), "yyyy/MM/dd pp")
				: "N/A",
			formatType: "date",
		},
	] as const;
