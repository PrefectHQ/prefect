import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { buildPaginateFlowRunsQuery } from "@/api/flow-runs";
import { TagsSelect } from "@/components/ui/tags-select";

type FlowRunTagsSelectProps = {
	value?: string[];
	onChange?: (tags: string[]) => void;
	placeholder?: string;
	id?: string;
};

export function FlowRunTagsSelect({
	value = [],
	onChange,
	placeholder = "All tags",
	id,
}: FlowRunTagsSelectProps) {
	// Fetch a recent page of flow runs to derive tag suggestions
	const { data } = useQuery(
		buildPaginateFlowRunsQuery({
			page: 1,
			limit: 100,
			sort: "START_TIME_DESC",
		}),
	);

	const suggestions = useMemo(() => {
		const all = new Set<string>();
		(data?.results ?? []).forEach((flowRun) => {
			(flowRun.tags ?? []).forEach((tag) => {
				all.add(tag);
			});
		});
		return Array.from(all).sort((a, b) => a.localeCompare(b));
	}, [data?.results]);

	return (
		<TagsSelect
			aria-label="Flow run tags"
			id={id}
			onChange={onChange}
			placeholder={placeholder}
			suggestions={suggestions}
			value={value}
		/>
	);
}

FlowRunTagsSelect.displayName = "FlowRunTagsSelect";
