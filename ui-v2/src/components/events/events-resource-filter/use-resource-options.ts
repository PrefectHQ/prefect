import { useQueries } from "@tanstack/react-query";
import { useMemo } from "react";
import { buildListAutomationsQuery } from "@/api/automations";
import { buildListFilterBlockDocumentsQuery } from "@/api/block-documents";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import { buildListFlowsQuery } from "@/api/flows";
import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
import { buildFilterWorkQueuesQuery } from "@/api/work-queues";

export type ResourceOption = {
	id: string;
	name: string;
	type:
		| "automation"
		| "block"
		| "deployment"
		| "flow"
		| "work-pool"
		| "work-queue";
	resourceId: string;
};

export const useResourceOptions = (): { resourceOptions: ResourceOption[] } => {
	const [
		{ data: automations },
		{ data: blocks },
		{ data: deployments },
		{ data: flows },
		{ data: workPools },
		{ data: workQueues },
	] = useQueries({
		queries: [
			buildListAutomationsQuery(),
			buildListFilterBlockDocumentsQuery(),
			buildFilterDeploymentsQuery(),
			buildListFlowsQuery(),
			buildFilterWorkPoolsQuery(),
			buildFilterWorkQueuesQuery(),
		],
	});

	const resourceOptions = useMemo(() => {
		const options: ResourceOption[] = [];

		for (const a of automations ?? []) {
			options.push({
				id: a.id,
				name: a.name,
				type: "automation",
				resourceId: `prefect.automation.${a.id}`,
			});
		}

		for (const b of blocks ?? []) {
			options.push({
				id: b.id,
				name: b.name ?? "",
				type: "block",
				resourceId: `prefect.block-document.${b.id}`,
			});
		}

		for (const d of deployments ?? []) {
			options.push({
				id: d.id,
				name: d.name,
				type: "deployment",
				resourceId: `prefect.deployment.${d.id}`,
			});
		}

		for (const f of flows ?? []) {
			options.push({
				id: f.id,
				name: f.name,
				type: "flow",
				resourceId: `prefect.flow.${f.id}`,
			});
		}

		for (const wp of workPools ?? []) {
			options.push({
				id: wp.name,
				name: wp.name,
				type: "work-pool",
				resourceId: `prefect.work-pool.${wp.name}`,
			});
		}

		for (const wq of workQueues ?? []) {
			options.push({
				id: wq.id,
				name: wq.name,
				type: "work-queue",
				resourceId: `prefect.work-queue.${wq.id}`,
			});
		}

		return options;
	}, [automations, blocks, deployments, flows, workPools, workQueues]);

	return { resourceOptions };
};
