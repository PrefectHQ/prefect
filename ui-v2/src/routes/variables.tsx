import { createQueryService } from "@/api/service";
import { useSuspenseQuery } from "@tanstack/react-query";
import { VariablesPage } from "@/components/variables/page";
import { createFileRoute } from "@tanstack/react-router";
import type { components } from "@/api/prefect";

export const Route = createFileRoute("/variables")({
	component: VariablesRoute,
});

function VariablesRoute() {
	const { data } = useSuspenseQuery({
		queryKey: ["variables"],
		queryFn: async () =>
			await createQueryService().POST("/variables/filter", {}),
	});
	console.log(data);
	return (
		<VariablesPage
			variables={data.data as components["schemas"]["Variable"][]}
		/>
	);
}
