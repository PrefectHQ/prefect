import { z } from "zod";

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
	})
	.and(
		z.union([
			z.object({ source: z.literal("inferred") }),
			z.object({
				deployment_id: z.string(),
				job_variables: z.record(z.unknown()),
				parameters: z.record(z.unknown()),
				source: z.literal("selected"),
			}),
		]),
	);

const DeploymentsSchema = z
	.object({
		type: z.enum(["pause-deployment", "resume-deployment"]),
	})
	.and(
		z.union([
			z.object({ source: z.literal("inferred") }),
			z.object({
				deployment_id: z.string(z.string()),
				source: z.literal("selected"),
			}),
		]),
	);

const WorkQueueSchema = z
	.object({
		type: z.enum(["pause-work-queue", "resume-work-queue"]),
	})
	.and(
		z.union([
			z.object({ source: z.literal("inferred") }),
			z.object({
				source: z.literal("selected"),
				work_queue_id: z.string(),
			}),
		]),
	);

const WorkPoolSchema = z
	.object({
		type: z.enum(["pause-work-pool", "resume-work-pool"]),
	})
	.and(
		z.union([
			z.object({ source: z.literal("inferred") }),
			z.object({ source: z.literal("selected"), work_pool_id: z.string() }),
		]),
	);

const AutomationSchema = z
	.object({
		type: z.enum(["pause-automation", "resume-automation"]),
	})
	.and(
		z.union([
			z.object({
				automation_id: z.null(),
				source: z.literal("inferred"),
			}),
			z.object({
				automation_id: z.string(),
				source: z.literal("selected"),
			}),
		]),
	);

const SendNotificationSchema = z.object({
	type: z.literal("send-notification"),
	block_document_id: z.string(),
	body: z.string(),
	subject: z.string(),
});

export const ActionsSchema = z.union([
	ChangeFlowRunStateSchema,
	DeploymentsSchema,
	RunDeploymentsSchema,
	WorkPoolSchema,
	WorkQueueSchema,
	AutomationSchema,
	SendNotificationSchema,
	FlowRunSchema,
]);

export type ActionsSchema = z.infer<typeof ActionsSchema>;
