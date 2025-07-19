import { z } from "zod";
import type { WorkPoolFormValues } from "../types";

// Validation schemas for each step
export const infrastructureTypeSchema = z.object({
	type: z
		.string({ required_error: "Infrastructure type is required" })
		.min(1, "Infrastructure type is required"),
});

export const informationSchema = z.object({
	name: z
		.string({ required_error: "Name is required" })
		.min(1, "Name is required")
		.regex(
			/^[a-zA-Z0-9_-]+$/,
			"Name can only contain letters, numbers, hyphens, and underscores",
		)
		.refine(
			(value) => !value.toLowerCase().startsWith("prefect"),
			'Work pools starting with "prefect" are reserved for internal use.',
		),
	description: z.string().optional(),
	concurrencyLimit: z.number().int().min(0).nullable().optional(),
});

export const configurationSchema = z.object({
	baseJobTemplate: z.record(z.unknown()).optional(),
});

// Complete schema combining all steps
export const workPoolSchema = z.object({
	type: infrastructureTypeSchema.shape.type,
	name: informationSchema.shape.name,
	description: informationSchema.shape.description,
	concurrencyLimit: informationSchema.shape.concurrencyLimit,
	baseJobTemplate: configurationSchema.shape.baseJobTemplate,
	isPaused: z.boolean().optional(),
});

export type WorkPoolSchema = z.infer<typeof workPoolSchema>;

export const useWorkPoolValidation = () => {
	const validateInfrastructureType = (data: WorkPoolFormValues) => {
		try {
			infrastructureTypeSchema.parse({ type: data.type });
			return { isValid: true, errors: {} };
		} catch (error) {
			if (error instanceof z.ZodError) {
				return {
					isValid: false,
					errors: error.flatten().fieldErrors,
				};
			}
			return { isValid: false, errors: {} };
		}
	};

	const validateInformation = (data: WorkPoolFormValues) => {
		try {
			informationSchema.parse({
				name: data.name,
				description: data.description,
				concurrencyLimit: data.concurrencyLimit,
			});
			return { isValid: true, errors: {} };
		} catch (error) {
			if (error instanceof z.ZodError) {
				return {
					isValid: false,
					errors: error.flatten().fieldErrors,
				};
			}
			return { isValid: false, errors: {} };
		}
	};

	const validateConfiguration = (data: WorkPoolFormValues) => {
		try {
			configurationSchema.parse({
				baseJobTemplate: data.baseJobTemplate,
			});
			return { isValid: true, errors: {} };
		} catch (error) {
			if (error instanceof z.ZodError) {
				return {
					isValid: false,
					errors: error.flatten().fieldErrors,
				};
			}
			return { isValid: false, errors: {} };
		}
	};

	const validateAll = (data: WorkPoolFormValues) => {
		try {
			workPoolSchema.parse(data);
			return { isValid: true, errors: {} };
		} catch (error) {
			if (error instanceof z.ZodError) {
				return {
					isValid: false,
					errors: error.flatten().fieldErrors,
				};
			}
			return { isValid: false, errors: {} };
		}
	};

	return {
		validateInfrastructureType,
		validateInformation,
		validateConfiguration,
		validateAll,
		schemas: {
			infrastructureType: infrastructureTypeSchema,
			information: informationSchema,
			configuration: configurationSchema,
			complete: workPoolSchema,
		},
	};
};
