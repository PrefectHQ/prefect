import type { components } from "@/api/prefect";
import type { PrefectApiClient } from "../api-client";

export type BlockDocument = components["schemas"]["BlockDocument"];
export type BlockType = components["schemas"]["BlockType"];
export type BlockSchema = components["schemas"]["BlockSchema"];

export async function listBlockTypes(
	client: PrefectApiClient,
): Promise<BlockType[]> {
	const { data, error } = await client.POST("/block_types/filter", {
		body: {},
	});
	if (error) {
		throw new Error(`Failed to list block types: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function getBlockTypeBySlug(
	client: PrefectApiClient,
	slug: string,
): Promise<BlockType> {
	const { data, error } = await client.GET("/block_types/slug/{slug}", {
		params: { path: { slug } },
	});
	if (error) {
		throw new Error(`Failed to get block type: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function listBlockSchemas(
	client: PrefectApiClient,
	blockTypeId: string,
): Promise<BlockSchema[]> {
	const { data, error } = await client.POST("/block_schemas/filter", {
		body: {
			block_schemas: {
				block_type_id: { any_: [blockTypeId] },
			},
		},
	});
	if (error) {
		throw new Error(`Failed to list block schemas: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function listBlockDocuments(
	client: PrefectApiClient,
): Promise<BlockDocument[]> {
	const { data, error } = await client.POST("/block_documents/filter", {
		body: {
			include_secrets: false,
		},
	});
	if (error) {
		throw new Error(`Failed to list block documents: ${JSON.stringify(error)}`);
	}
	return data;
}

export async function createBlockDocument(
	client: PrefectApiClient,
	params: {
		name: string;
		blockTypeId: string;
		blockSchemaId: string;
		data: Record<string, unknown>;
	},
): Promise<BlockDocument> {
	const { data, error } = await client.POST("/block_documents/", {
		body: {
			name: params.name,
			block_type_id: params.blockTypeId,
			block_schema_id: params.blockSchemaId,
			data: params.data,
			is_anonymous: false,
		},
	});
	if (error) {
		throw new Error(
			`Failed to create block document: ${JSON.stringify(error)}`,
		);
	}
	return data;
}

export async function deleteBlockDocument(
	client: PrefectApiClient,
	id: string,
	options?: { ignoreNotFound?: boolean },
): Promise<void> {
	const { error } = await client.DELETE("/block_documents/{id}", {
		params: { path: { id } },
	});
	if (error) {
		const isNotFound =
			typeof error === "object" &&
			error !== null &&
			"detail" in error &&
			String(error.detail).includes("not found");
		if (options?.ignoreNotFound && isNotFound) {
			return;
		}
		throw new Error(
			`Failed to delete block document: ${JSON.stringify(error)}`,
		);
	}
}

export async function cleanupBlockDocuments(
	client: PrefectApiClient,
	namePrefix: string,
): Promise<void> {
	const documents = await listBlockDocuments(client);
	const toDelete = documents.filter((d) => d.name?.startsWith(namePrefix));
	await Promise.all(
		toDelete.map((d) =>
			deleteBlockDocument(client, d.id, { ignoreNotFound: true }),
		),
	);
}
