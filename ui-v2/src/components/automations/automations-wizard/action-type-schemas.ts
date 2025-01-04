import { z } from "zod";

const FlowRunSchema = z.object({
	type: z.enum(["cancel-flow-run", "suspend-flow-run", "resume-flow-run"]),
});

const ChangeFlowRunStateSchema = z
	.object({
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
	})
	.strict();

// TODO
const DeploymentsSchema = z
	.object({
		type: z.enum(["run-deployment", "pause-deployment", "resume-deployment"]),
	})
	.strict();

// TODO
const WorkQueueSchema = z
	.object({
		type: z.enum(["pause-work-queue", "resume-work-queue"]),
	})
	.strict();

// TODO
const WorkPoolSchema = z
	.object({
		type: z.enum(["pause-work-pool", "resume-work-pool"]),
	})
	.strict();

// TODO
const AutomationSchema = z
	.object({
		type: z.enum(["pause-automation", "resume-automation"]),
	})
	.strict();

// TODO
const SendNotificationSchema = z
	.object({ type: z.literal("send-notification") })
	.strict();

export const ActionsSchema = z.union([
	ChangeFlowRunStateSchema,
	DeploymentsSchema,
	WorkPoolSchema,
	WorkQueueSchema,
	AutomationSchema,
	SendNotificationSchema,
	FlowRunSchema,
]);

export type ActionsSchema = z.infer<typeof ActionsSchema>;
