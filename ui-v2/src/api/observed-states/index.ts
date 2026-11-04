import { queryOptions, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { STATE_NAMES } from "@/api/flow-runs/constants";
import type { paths } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import useDebounce from "@/hooks/use-debounce";

type ObservedStatesQuery = NonNullable<
	paths["/observed-states"]["get"]["parameters"]["query"]
>;

export const buildObservedStatesQuery = (params: ObservedStatesQuery = {}) =>
	queryOptions({
		queryKey: ["observed-states", params],
		queryFn: async () => {
			const service = await getQueryService();
			const { data } = await service.GET("/observed-states", {
				params: { query: params },
			});
			return data ?? [];
		},
		staleTime: 30_000,
		refetchInterval: 30_000,
	});

// Keep built-ins and selected names available even when discovery is capped,
// still loading, unavailable, or the selected observation has been deleted.
export function useStateOptions(
	search: string,
	selected: string[],
	enabled: boolean,
) {
	const query = useDebounce(search.trim().slice(0, 100), 300);
	const result = useQuery({
		...buildObservedStatesQuery({ query, order_by: "NAME_ASC" }),
		enabled,
	});
	const names = useMemo(() => {
		const prefix = search.trim().toLowerCase();
		const local = [...STATE_NAMES, ...selected].filter((name) =>
			name.toLowerCase().startsWith(prefix),
		);
		const observed =
			query.toLowerCase() === prefix.slice(0, 100)
				? (result.data ?? []).filter(
						(state) =>
							prefix.length <= 100 ||
							state.state_name.toLowerCase().startsWith(prefix),
					)
				: [];
		return [...new Set([...local, ...observed.map((s) => s.state_name)])];
	}, [search, selected, result.data, query]);
	return {
		data: result.data,
		isFetching: result.isFetching,
		isError: result.isError,
		names,
	};
}
