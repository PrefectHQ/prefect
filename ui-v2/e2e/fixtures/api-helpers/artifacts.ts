import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type Artifact = components["schemas"]["Artifact"];

export async function createArtifact(
	client: PrefectApiClient,
	params: {
		key?: string;
		type?: string;
		description?: string;
		data?: unknown;
		flowRunId?: string;
		taskRunId?: string;
	},
): Promise<Artifact> {
	const { data, error } = await client.POST("/artifacts/", {
		body: {
			key: params.key,
			type: params.type,
			description: params.description,
			data: params.data,
			flow_run_id: params.flowRunId,
			task_run_id: params.taskRunId,
		},
	});
	if (error) {
		throw new Error(`Failed to create artifact: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function createMarkdownArtifact(
	client: PrefectApiClient,
	params: {
		key: string;
		markdown: string;
		description?: string;
		flowRunId?: string;
	},
): Promise<Artifact> {
	return createArtifact(client, {
		key: params.key,
		type: "markdown",
		data: params.markdown,
		description: params.description,
		flowRunId: params.flowRunId,
	});
}

export async function createTableArtifact(
	client: PrefectApiClient,
	params: {
		key: string;
		table: Record<string, unknown>[];
		description?: string;
		flowRunId?: string;
	},
): Promise<Artifact> {
	return createArtifact(client, {
		key: params.key,
		type: "table",
		data: JSON.stringify(params.table),
		description: params.description,
		flowRunId: params.flowRunId,
	});
}

export async function createLinkArtifact(
	client: PrefectApiClient,
	params: {
		key: string;
		link: string;
		linkText?: string;
		description?: string;
		flowRunId?: string;
	},
): Promise<Artifact> {
	const text = params.linkText ?? params.link;
	return createArtifact(client, {
		key: params.key,
		type: "markdown",
		data: `[${text}](${params.link})`,
		description: params.description,
		flowRunId: params.flowRunId,
	});
}

export async function listArtifacts(
	client: PrefectApiClient,
): Promise<Artifact[]> {
	const { data, error } = await client.POST("/artifacts/filter", {
		body: {
			sort: "CREATED_DESC",
			limit: 100,
			offset: 0,
		},
	});
	if (error) {
		throw new Error(`Failed to list artifacts: ${JSON.stringify(error)}`);
	}
	return data ?? [];
}

export async function deleteArtifact(
	client: PrefectApiClient,
	id: string,
): Promise<void> {
	const { error } = await client.DELETE("/artifacts/{id}", {
		params: { path: { id } },
	});
	if (error) {
		throw new Error(`Failed to delete artifact: ${JSON.stringify(error)}`);
	}
}

export async function cleanupArtifacts(
	client: PrefectApiClient,
	prefix: string,
): Promise<void> {
	const artifacts = await listArtifacts(client);
	const toDelete = artifacts.filter(
		(a): a is Artifact & { id: string } =>
			!!a.id && !!a.key?.startsWith(prefix),
	);
	await Promise.all(
		toDelete.map((a) => deleteArtifact(client, a.id).catch(() => {})),
	);
}
