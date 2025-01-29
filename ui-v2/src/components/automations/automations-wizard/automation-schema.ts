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

export const AutomationWizardSchema = z.object({
	name: z.string(),
	description: z.string().optional(),
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
