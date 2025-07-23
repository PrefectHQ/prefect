import { z } from "zod";

export const workPoolInformationSchema = z.object({
	name: z
		.string()
		.min(1, "Name is required")
		.refine(
			(value) => !value.toLowerCase().startsWith("prefect"),
			"Work pools starting with 'prefect' are reserved for internal use.",
		),
	description: z.string().nullable().optional(),
	concurrencyLimit: z.number().min(0).nullable().optional(),
});

export type WorkPoolInformationFormValues = z.infer<
	typeof workPoolInformationSchema
>;
