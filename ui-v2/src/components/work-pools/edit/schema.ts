import { z } from "zod";
import type { WorkerBaseJobTemplate } from "@/components/work-pools/types";

export type { WorkerBaseJobTemplate };

export const workPoolEditSchema = z.object({
	description: z.string().nullable().optional(),
	concurrencyLimit: z.number().min(0).nullable().optional(),
	baseJobTemplate: z.record(z.unknown()).optional(),
});

export type WorkPoolEditFormValues = z.infer<typeof workPoolEditSchema>;
