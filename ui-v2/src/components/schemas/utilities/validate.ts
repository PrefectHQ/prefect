import { getQueryService } from "@/api/service";

export async function validateSchemaValues(
	schema: Record<string, unknown>,
	values: Record<string, unknown>,
) {
	const { data } = await getQueryService().POST("/ui/schemas/validate", {
		body: {
			schema,
			values,
		},
	});

	if (!data) {
		throw new Error('"data" expected');
	}
	return data;
}
