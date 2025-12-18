import { z } from "zod";
import type { WorkerBaseJobTemplate } from "@/components/work-pools/types";

export type { WorkerBaseJobTemplate };

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
