import { useQueries, useQuery } from "@tanstack/react-query";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import { buildListTaskRunsQuery } from "@/api/task-runs";
import {
	type ArtifactsFilter,
	type ArtifactWithFlowRunAndTaskRun,
	buildGetArtifactQuery,
	buildListArtifactsQuery,
} from "..";

export const useFilterArtifactsFlowTaskRuns = (filter: ArtifactsFilter) => {
	const { data: artifacts } = useQuery(buildListArtifactsQuery(filter));

	const flowRunIds = artifacts
		?.map((artifact) => artifact.flow_run_id)
		.filter((val) => val != null && val !== undefined);
	const taskRunIds = artifacts
		?.map((artifact) => artifact.task_run_id)
		.filter((val) => val != null && val !== undefined);

	const { flowRuns, taskRuns } = useQueries({
		queries: [
			buildFilterFlowRunsQuery({
				flow_runs: {
					operator: "and_",
					id: {
						any_: flowRunIds,
					},
				},
				sort: "ID_DESC",
				offset: 0,
			}),
			buildListTaskRunsQuery({
				task_runs: {
					operator: "and_",
					id: {
						any_: taskRunIds,
					},
				},
				sort: "ID_DESC",
				offset: 0,
			}),
		],
		combine: (data) => {
			const [flowRuns, taskRuns] = data;
			return {
				flowRuns: flowRuns.data,
				taskRuns: taskRuns.data,
			};
		},
	});

	const artifactsWithMetadata = artifacts?.map((artifact) => {
		const flowRun = flowRuns?.find(
			(flowRun) => flowRun.id === artifact.flow_run_id,
		);
		const taskRun = taskRuns?.find(
			(taskRun) => taskRun.id === artifact.task_run_id,
		);

		return {
			...artifact,
			flow_run: flowRun,
			task_run: taskRun,
		};
	});

	return artifactsWithMetadata as ArtifactWithFlowRunAndTaskRun[];
};

export const useGetArtifactFlowTaskRuns = (artifactId: string) => {
	const { data: artifact } = useQuery(buildGetArtifactQuery(artifactId));

	const flowRunId = artifact?.flow_run_id;
	const taskRunId = artifact?.task_run_id;
	const { flowRuns, taskRuns } = useQueries({
		queries: [
			buildFilterFlowRunsQuery({
				flow_runs: {
					operator: "and_",
					id: {
						any_: [flowRunId ?? ""],
					},
				},
				sort: "ID_DESC",
				offset: 0,
			}),
			buildListTaskRunsQuery({
				task_runs: {
					operator: "and_",
					id: {
						any_: [taskRunId ?? ""],
					},
				},
				sort: "ID_DESC",
				offset: 0,
			}),
		],
		combine: (data) => {
			const [flowRuns, taskRuns] = data;
			return {
				flowRuns: flowRuns.data,
				taskRuns: taskRuns.data,
			};
		},
	});

	return {
		...artifact,
		flow_run: flowRuns?.[0],
		task_run: taskRuns?.[0],
	} as ArtifactWithFlowRunAndTaskRun;
};
