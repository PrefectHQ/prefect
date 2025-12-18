import type { PrefectSchemaObject } from "@/components/schemas/types/schemas";

export type WorkerBaseJobTemplate = {
	job_configuration?: Record<string, unknown>;
	variables?: PrefectSchemaObject;
};
