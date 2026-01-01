import { z } from "zod";
export const UNASSIGNED = "UNASSIGNED";

//----- Actions
const DoNothingSchema = z.object({ type: z.literal("do-nothing") });

const FlowRunSchema = z.object({
	type: z.enum(["cancel-flow-run", "suspend-flow-run", "resume-flow-run"]),
});

const ChangeFlowRunStateSchema = z.object({
	type: z.literal("change-flow-run-state"),
	state: z.enum([
		"COMPLETED",
		"RUNNING",
		"SCHEDULED",
		"PENDING",
		"FAILED",
		"CANCELLED",
		"CANCELLING",
		"CRASHED",
		"PAUSED",
	]),
	name: z.string().optional(),
	message: z.string().optional(),
});

const RunDeploymentsSchema = z
	.object({
		type: z.literal("run-deployment"),
		deployment_id: z.string().or(z.literal(UNASSIGNED)),
		job_variables: z.record(z.unknown()).optional(),
		parameters: z.record(z.unknown()).optional(),
	})
	.transform((schema) => ({
		...schema,
		...(schema.deployment_id === UNASSIGNED
			? ({ source: "inferred", deployment_id: null } as const)
			: ({ source: "selected", deployment_id: schema.deployment_id } as const)),
	}));

const DeploymentsSchema = z
	.object({
		type: z.enum(["pause-deployment", "resume-deployment"]),
		/** nb: Because shadcn MUST have a non empty string as a value, use UNASSIGNED to indicate that this will turn to a null value */
		deployment_id: z.string().or(z.literal(UNASSIGNED)),
	})
	.transform((schema) => ({
		type: schema.type,
		...(schema.deployment_id === UNASSIGNED
			? ({ source: "inferred", deployment_id: null } as const)
			: ({ source: "selected", deployment_id: schema.deployment_id } as const)),
	}));

const WorkQueueSchema = z
	.object({
		type: z.enum(["pause-work-queue", "resume-work-queue"]),
		/** nb: Because shadcn MUST have a non empty string as a value, use UNASSIGNED to indicate that this will turn to a null value */
		work_queue_id: z.string().or(z.literal(UNASSIGNED)),
	})
	.transform((schema) => ({
		type: schema.type,
		...(schema.work_queue_id === UNASSIGNED
			? ({ source: "inferred", work_queue_id: null } as const)
			: ({ source: "selected", work_queue_id: schema.work_queue_id } as const)),
	}));

const WorkPoolSchema = z
	.object({
		type: z.enum(["pause-work-pool", "resume-work-pool"]),
		/** nb: Because shadcn MUST have a non empty string as a value, use UNASSIGNED to indicate that this will turn to a null value */
		work_pool_id: z.string().or(z.literal(UNASSIGNED)),
	})
	.transform((schema) => ({
		type: schema.type,
		...(schema.work_pool_id === UNASSIGNED
			? ({ source: "inferred", work_pool_id: null } as const)
			: ({ source: "selected", work_pool_id: schema.work_pool_id } as const)),
	}));

const AutomationSchema = z
	.object({
		type: z.enum(["pause-automation", "resume-automation"]),
		/** nb: Because shadcn MUST have a non empty string as a value, use UNASSIGNED to indicate that this will turn to a null value */
		automation_id: z.string().or(z.literal(UNASSIGNED)),
	})
	.transform((schema) => ({
		type: schema.type,
		...(schema.automation_id === UNASSIGNED
			? ({ source: "inferred", automation_id: null } as const)
			: ({ source: "selected", automation_id: schema.automation_id } as const)),
	}));

const SendNotificationSchema = z.object({
	type: z.literal("send-notification"),
	block_document_id: z.string(),
	body: z.string(),
	subject: z.string(),
});

//----- Triggers

// Trigger template type (for UI selection)
export const TriggerTemplateSchema = z.enum([
	"deployment-status",
	"flow-run-state",
	"work-pool-status",
	"work-queue-status",
	"custom",
]);
export type TriggerTemplate = z.infer<typeof TriggerTemplateSchema>;

// Trigger posture
const TriggerPostureSchema = z.enum(["Reactive", "Proactive"]);
export type TriggerPosture = z.infer<typeof TriggerPostureSchema>;

// Event trigger schema (the primary trigger type for form mode)
// Resource specification schema (for match conditions)
const ResourceSpecificationSchema = z.record(
	z.union([z.string(), z.array(z.string())]),
);

export const EventTriggerSchema = z.object({
	type: z.literal("event"),
	posture: TriggerPostureSchema,
	threshold: z.number().min(1).default(1),
	within: z.number().min(0).default(0),
	// Match conditions
	match: ResourceSpecificationSchema.optional(),
	match_related: ResourceSpecificationSchema.optional(),
	for_each: z.array(z.string()).optional(),
	after: z.array(z.string()).optional(),
	expect: z.array(z.string()).optional(),
});
export type EventTrigger = z.output<typeof EventTriggerSchema>;
export type EventTriggerInput = z.input<typeof EventTriggerSchema>;

// Output types (after parsing - all defaults are applied, fields are required)
export type CompoundTrigger = {
	type: "compound";
	triggers: Trigger[];
	require: number | "any" | "all";
	within: number;
};

export type SequenceTrigger = {
	type: "sequence";
	triggers: Trigger[];
	within: number;
};

export type Trigger = EventTrigger | CompoundTrigger | SequenceTrigger;

// Input types (before parsing - defaulted fields are optional)
export type CompoundTriggerInput = {
	type: "compound";
	triggers: TriggerInput[];
	require?: number | "any" | "all";
	within?: number;
};

export type SequenceTriggerInput = {
	type: "sequence";
	triggers: TriggerInput[];
	within?: number;
};

export type TriggerInput =
	| EventTriggerInput
	| CompoundTriggerInput
	| SequenceTriggerInput;

// Recursive trigger schemas with explicit type annotations
// Using z.ZodType<Output, z.ZodTypeDef, Input> to handle input/output type differences from defaults

export const TriggerSchema: z.ZodType<Trigger, z.ZodTypeDef, TriggerInput> =
	z.lazy(() =>
		z.union([EventTriggerSchema, CompoundTriggerSchema, SequenceTriggerSchema]),
	);

export const CompoundTriggerSchema: z.ZodType<
	CompoundTrigger,
	z.ZodTypeDef,
	CompoundTriggerInput
> = z.lazy(() =>
	z.object({
		type: z.literal("compound"),
		triggers: z.array(TriggerSchema),
		require: z
			.union([z.number().min(1), z.literal("any"), z.literal("all")])
			.default("all"),
		within: z.number().min(0).default(0),
	}),
);

export const SequenceTriggerSchema: z.ZodType<
	SequenceTrigger,
	z.ZodTypeDef,
	SequenceTriggerInput
> = z.lazy(() =>
	z.object({
		type: z.literal("sequence"),
		triggers: z.array(TriggerSchema),
		within: z.number().min(0).default(0),
	}),
);

export const AutomationWizardSchema = z.object({
	name: z.string().min(1, "Name is required"),
	description: z.string().optional(),
	triggerTemplate: TriggerTemplateSchema.optional(),
	trigger: TriggerSchema,
	actions: z.array(
		z.union([
			DoNothingSchema,
			ChangeFlowRunStateSchema,
			DeploymentsSchema,
			RunDeploymentsSchema,
			WorkPoolSchema,
			WorkQueueSchema,
			AutomationSchema,
			SendNotificationSchema,
			FlowRunSchema,
		]),
	),
});
export type AutomationWizardSchema = z.infer<typeof AutomationWizardSchema>;
export type ActionsSchema = AutomationWizardSchema["actions"][number];
export type ActionType = AutomationWizardSchema["actions"][number]["type"];
