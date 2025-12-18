import { z } from "zod";
import type { PrefectSchemaObject } from "@/components/schemas/types/schemas";

export type WorkerBaseJobTemplate = {
	job_configuration?: Record<string, unknown>;
	variables?: PrefectSchemaObject;
};

export const workPoolEditSchema = z.object({
	description: z.string().nullable().optional(),
	concurrencyLimit: z.number().min(0).nullable().optional(),
	baseJobTemplate: z.record(z.unknown()).optional(),
});

export type WorkPoolEditFormValues = z.infer<typeof workPoolEditSchema>;
