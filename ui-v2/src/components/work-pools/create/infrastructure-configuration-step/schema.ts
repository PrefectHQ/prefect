import { z } from "zod";
import type { PrefectSchemaObject } from "@/components/schemas/types/schemas";

export type WorkerBaseJobTemplate = {
	job_configuration?: Record<string, unknown>;
	variables?: PrefectSchemaObject;
};

export const infrastructureConfigurationSchema = z.object({
	baseJobTemplate: z.record(z.unknown()).optional(),
});

export type InfrastructureConfigurationFormValues = z.infer<
	typeof infrastructureConfigurationSchema
>;

export type WorkPoolFormValues = {
	name?: string;
	description?: string | null;
	type?: string;
	isPaused?: boolean;
	concurrencyLimit?: number | null;
	baseJobTemplate?: WorkerBaseJobTemplate;
};
