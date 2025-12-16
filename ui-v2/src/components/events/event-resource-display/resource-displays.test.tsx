import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { describe, expect, it } from "vitest";
import {
	createFakeAutomation,
	createFakeBlockDocument,
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
	createFakeTaskRun,
	createFakeTaskRunConcurrencyLimit,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { ResolvedResourceDisplay } from "./resolved-resource-display";
import {
	AutomationResourceDisplay,
	BlockDocumentResourceDisplay,
	ConcurrencyLimitResourceDisplay,
	DeploymentResourceDisplay,
	FlowResourceDisplay,
	FlowRunResourceDisplay,
	TaskRunResourceDisplay,
	WorkPoolResourceDisplay,
	WorkQueueResourceDisplay,
} from "./resource-displays";

const mockFlowRun = createFakeFlowRun({
	id: "flow-run-123",
	name: "my-flow-run",
});
const mockTaskRun = createFakeTaskRun({
	id: "task-run-123",
	name: "my-task-run",
});
const mockDeployment = createFakeDeployment({
	id: "deployment-123",
	name: "my-deployment",
});
const mockFlow = createFakeFlow({ id: "flow-123", name: "my-flow" });
const mockWorkPool = createFakeWorkPool({
	name: "my-work-pool",
});
const mockWorkQueue = createFakeWorkQueue({
	id: "work-queue-123",
	name: "my-work-queue",
});
const mockAutomation = createFakeAutomation({
	id: "automation-123",
	name: "my-automation",
});
const mockBlockDocument = createFakeBlockDocument({
	id: "block-document-123",
	name: "my-block",
});
const mockConcurrencyLimit = createFakeTaskRunConcurrencyLimit({
	id: "concurrency-limit-123",
	tag: "my-concurrency-limit",
});

const renderWithSuspense = (ui: React.ReactElement) => {
	return render(<Suspense fallback={<div>Loading...</div>}>{ui}</Suspense>, {
		wrapper: createWrapper(),
	});
};

describe("FlowRunResourceDisplay", () => {
	it("fetches and displays flow run name", async () => {
		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(mockFlowRun);
			}),
		);

		renderWithSuspense(<FlowRunResourceDisplay resourceId="flow-run-123" />);

		await waitFor(() => {
			expect(screen.getByText("my-flow-run")).toBeInTheDocument();
		});
	});
});

describe("TaskRunResourceDisplay", () => {
	it("fetches and displays task run name", async () => {
		server.use(
			http.get(buildApiUrl("/ui/task_runs/:id"), () => {
				return HttpResponse.json(mockTaskRun);
			}),
		);

		renderWithSuspense(<TaskRunResourceDisplay resourceId="task-run-123" />);

		await waitFor(() => {
			expect(screen.getByText("my-task-run")).toBeInTheDocument();
		});
	});
});

describe("DeploymentResourceDisplay", () => {
	it("fetches and displays deployment name", async () => {
		server.use(
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(mockDeployment);
			}),
		);

		renderWithSuspense(
			<DeploymentResourceDisplay resourceId="deployment-123" />,
		);

		await waitFor(() => {
			expect(screen.getByText("my-deployment")).toBeInTheDocument();
		});
	});
});

describe("FlowResourceDisplay", () => {
	it("fetches and displays flow name", async () => {
		server.use(
			http.get(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(mockFlow);
			}),
		);

		renderWithSuspense(<FlowResourceDisplay resourceId="flow-123" />);

		await waitFor(() => {
			expect(screen.getByText("my-flow")).toBeInTheDocument();
		});
	});
});

describe("WorkPoolResourceDisplay", () => {
	it("fetches and displays work pool name", async () => {
		server.use(
			http.get(buildApiUrl("/work_pools/:name"), () => {
				return HttpResponse.json(mockWorkPool);
			}),
		);

		renderWithSuspense(<WorkPoolResourceDisplay resourceId="my-work-pool" />);

		await waitFor(() => {
			expect(screen.getByText("my-work-pool")).toBeInTheDocument();
		});
	});
});

describe("WorkQueueResourceDisplay", () => {
	it("fetches and displays work queue name", async () => {
		server.use(
			http.get(buildApiUrl("/work_queues/:id"), () => {
				return HttpResponse.json(mockWorkQueue);
			}),
		);

		renderWithSuspense(
			<WorkQueueResourceDisplay resourceId="work-queue-123" />,
		);

		await waitFor(() => {
			expect(screen.getByText("my-work-queue")).toBeInTheDocument();
		});
	});
});

describe("AutomationResourceDisplay", () => {
	it("fetches and displays automation name", async () => {
		server.use(
			http.get(buildApiUrl("/automations/:id"), () => {
				return HttpResponse.json(mockAutomation);
			}),
		);

		renderWithSuspense(
			<AutomationResourceDisplay resourceId="automation-123" />,
		);

		await waitFor(() => {
			expect(screen.getByText("my-automation")).toBeInTheDocument();
		});
	});
});

describe("BlockDocumentResourceDisplay", () => {
	it("fetches and displays block document name", async () => {
		server.use(
			http.get(buildApiUrl("/block_documents/:id"), () => {
				return HttpResponse.json(mockBlockDocument);
			}),
		);

		renderWithSuspense(
			<BlockDocumentResourceDisplay resourceId="block-document-123" />,
		);

		await waitFor(() => {
			expect(screen.getByText("my-block")).toBeInTheDocument();
		});
	});
});

describe("ConcurrencyLimitResourceDisplay", () => {
	it("fetches and displays concurrency limit tag", async () => {
		server.use(
			http.get(buildApiUrl("/concurrency_limits/:id"), () => {
				return HttpResponse.json(mockConcurrencyLimit);
			}),
		);

		renderWithSuspense(
			<ConcurrencyLimitResourceDisplay resourceId="concurrency-limit-123" />,
		);

		await waitFor(() => {
			expect(screen.getByText("my-concurrency-limit")).toBeInTheDocument();
		});
	});
});

describe("ResolvedResourceDisplay", () => {
	it("renders FlowRunResourceDisplay for flow-run type", async () => {
		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(mockFlowRun);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay
				resourceType="flow-run"
				resourceId="flow-run-123"
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("my-flow-run")).toBeInTheDocument();
		});
	});

	it("renders TaskRunResourceDisplay for task-run type", async () => {
		server.use(
			http.get(buildApiUrl("/ui/task_runs/:id"), () => {
				return HttpResponse.json(mockTaskRun);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay
				resourceType="task-run"
				resourceId="task-run-123"
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("my-task-run")).toBeInTheDocument();
		});
	});

	it("renders DeploymentResourceDisplay for deployment type", async () => {
		server.use(
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(mockDeployment);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay
				resourceType="deployment"
				resourceId="deployment-123"
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("my-deployment")).toBeInTheDocument();
		});
	});

	it("renders FlowResourceDisplay for flow type", async () => {
		server.use(
			http.get(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(mockFlow);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay resourceType="flow" resourceId="flow-123" />,
		);

		await waitFor(() => {
			expect(screen.getByText("my-flow")).toBeInTheDocument();
		});
	});

	it("renders WorkPoolResourceDisplay for work-pool type", async () => {
		server.use(
			http.get(buildApiUrl("/work_pools/:name"), () => {
				return HttpResponse.json(mockWorkPool);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay
				resourceType="work-pool"
				resourceId="my-work-pool"
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("my-work-pool")).toBeInTheDocument();
		});
	});

	it("renders WorkQueueResourceDisplay for work-queue type", async () => {
		server.use(
			http.get(buildApiUrl("/work_queues/:id"), () => {
				return HttpResponse.json(mockWorkQueue);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay
				resourceType="work-queue"
				resourceId="work-queue-123"
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("my-work-queue")).toBeInTheDocument();
		});
	});

	it("renders AutomationResourceDisplay for automation type", async () => {
		server.use(
			http.get(buildApiUrl("/automations/:id"), () => {
				return HttpResponse.json(mockAutomation);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay
				resourceType="automation"
				resourceId="automation-123"
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("my-automation")).toBeInTheDocument();
		});
	});

	it("renders BlockDocumentResourceDisplay for block-document type", async () => {
		server.use(
			http.get(buildApiUrl("/block_documents/:id"), () => {
				return HttpResponse.json(mockBlockDocument);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay
				resourceType="block-document"
				resourceId="block-document-123"
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("my-block")).toBeInTheDocument();
		});
	});

	it("renders ConcurrencyLimitResourceDisplay for concurrency-limit type", async () => {
		server.use(
			http.get(buildApiUrl("/concurrency_limits/:id"), () => {
				return HttpResponse.json(mockConcurrencyLimit);
			}),
		);

		renderWithSuspense(
			<ResolvedResourceDisplay
				resourceType="concurrency-limit"
				resourceId="concurrency-limit-123"
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("my-concurrency-limit")).toBeInTheDocument();
		});
	});
});
