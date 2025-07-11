import type { Meta, StoryObj } from "@storybook/react";
import type { Automation } from "@/api/automations";
import type { BlockDocument } from "@/api/block-documents";
import type { Deployment } from "@/api/deployments";
import type { WorkPool } from "@/api/work-pools";
import type { WorkQueue } from "@/api/work-queues";
import {
	createFakeAutomation,
	createFakeBlockDocument,
	createFakeDeployment,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { routerDecorator } from "@/storybook/utils";
import { ActionDetails } from "./action-details";

const ACTIONS: Array<Automation["actions"][number]> = [
	{ type: "do-nothing" },
	{ type: "cancel-flow-run" },
	{ type: "suspend-flow-run" },
	{ type: "cancel-flow-run" },
	{ type: "resume-flow-run" },
	{ type: "run-deployment", deployment_id: null, source: "inferred" },
	{
		type: "run-deployment",
		deployment_id: "abc",
		source: "selected",
		parameters: { Hello: "World", Goodbye: "World" },
		job_variables: { var1: "abc", var2: { foo: "bar" } },
	},
	{ type: "pause-deployment", deployment_id: null, source: "inferred" },
	{ type: "pause-deployment", deployment_id: "abc", source: "selected" },
	{ type: "resume-deployment", deployment_id: null, source: "inferred" },
	{ type: "resume-deployment", deployment_id: "abc", source: "selected" },
	{ type: "pause-work-queue", work_queue_id: null, source: "inferred" },
	{ type: "pause-work-queue", work_queue_id: "abc", source: "selected" },
	{ type: "resume-work-queue", work_queue_id: null, source: "inferred" },
	{ type: "resume-work-queue", work_queue_id: "abc", source: "selected" },
	{ type: "pause-work-pool", work_pool_id: null, source: "inferred" },
	{ type: "pause-work-pool", work_pool_id: "abc", source: "selected" },
	{ type: "resume-work-pool", work_pool_id: null, source: "inferred" },
	{ type: "resume-work-pool", work_pool_id: "abc", source: "selected" },
	{ type: "pause-automation", automation_id: null, source: "inferred" },
	{ type: "pause-automation", automation_id: "abc", source: "selected" },
	{ type: "resume-automation", automation_id: null, source: "inferred" },
	{ type: "resume-automation", automation_id: "abc", source: "selected" },
	{
		type: "change-flow-run-state",
		state: "CANCELLED",
	},
	{
		type: "change-flow-run-state",
		state: "CANCELLING",
	},
	{
		type: "change-flow-run-state",
		state: "COMPLETED",
	},
	{
		type: "change-flow-run-state",
		state: "CRASHED",
	},
	{
		type: "change-flow-run-state",
		state: "FAILED",
	},
	{
		type: "change-flow-run-state",
		state: "PAUSED",
	},
	{
		type: "change-flow-run-state",
		state: "PENDING",
	},
	{
		type: "change-flow-run-state",
		state: "RUNNING",
		message: "My message",
		name: "My name",
	},
	{
		type: "change-flow-run-state",
		state: "SCHEDULED",
	},
	{
		type: "send-notification",
		block_document_id: "abc",
		body: "my_body",
		subject: "my_subject",
	},
	{
		type: "call-webhook",
		block_document_id: "abc",
		payload: "my_payload",
	},
];

const MOCK_AUTOMATIONS_MAP = new Map<string, Automation>([
	["abc", createFakeAutomation({ id: "abc" })],
]);

const MOCK_BLOCK_DOCUMENTS_MAP = new Map<string, BlockDocument>([
	["abc", createFakeBlockDocument({ id: "abc" })],
]);

const MOCK_DEPLOYMENTS_MAP = new Map<string, Deployment>([
	["abc", createFakeDeployment({ id: "abc" })],
]);

const MOCK_WORK_POOLS_MAP = new Map<string, WorkPool>([
	["abc", createFakeWorkPool({ id: "abc" })],
]);

const MOCK_WORK_QUEUES_MAP = new Map<string, WorkQueue>([
	["abc", createFakeWorkQueue({ id: "abc" })],
]);

const meta = {
	title: "Components/Automations/ActionDetails",
	component: ActionDetailsStory,
	decorators: [routerDecorator],
} satisfies Meta<typeof ActionDetails>;

export default meta;

export const Story: StoryObj = {
	name: "ActionDetails",
};

function ActionDetailsStory() {
	return (
		<ul className="flex flex-col gap-4">
			{ACTIONS.map((action) => (
				<li key={action.type}>
					<ActionDetails
						action={action}
						automationsMap={MOCK_AUTOMATIONS_MAP}
						blockDocumentsMap={MOCK_BLOCK_DOCUMENTS_MAP}
						deploymentsMap={MOCK_DEPLOYMENTS_MAP}
						workPoolsMap={MOCK_WORK_POOLS_MAP}
						workQueuesMap={MOCK_WORK_QUEUES_MAP}
					/>
				</li>
			))}
		</ul>
	);
}
