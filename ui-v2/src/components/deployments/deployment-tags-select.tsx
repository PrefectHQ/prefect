import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import { TagsSelect } from "@/components/ui/tags-select";

// Stable filter so the query key does not change between renders. Suggestions
// come from the unfiltered set of deployments, like the legacy UI. The request
// gives no limit, because the server rejects a limit that is more than
// PREFECT_SERVER_API_DEFAULT_LIMIT.
const SUGGESTIONS_FILTER = {
	offset: 0,
	sort: "NAME_ASC",
} as const;

type DeploymentTagsSelectProps = {
	value?: string[];
	onChange?: (tags: string[]) => void;
	placeholder?: string;
	id?: string;
};

export function DeploymentTagsSelect({
	value = [],
	onChange,
	placeholder = "Filter by tags",
	id,
}: DeploymentTagsSelectProps) {
	const { data: deployments } = useQuery(
		buildFilterDeploymentsQuery(SUGGESTIONS_FILTER),
	);

	const suggestions = useMemo(() => {
		const all = new Set<string>();
		(deployments ?? []).forEach((deployment) => {
			(deployment.tags ?? []).forEach((tag) => {
				all.add(tag);
			});
		});
		return Array.from(all).sort((a, b) => a.localeCompare(b));
	}, [deployments]);

	return (
		<TagsSelect
			aria-label={placeholder}
			id={id}
			onChange={onChange}
			placeholder={placeholder}
			suggestions={suggestions}
			value={value}
		/>
	);
}
