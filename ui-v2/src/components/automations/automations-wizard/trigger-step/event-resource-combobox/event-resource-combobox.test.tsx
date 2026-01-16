import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeAutomation } from "@/mocks/create-fake-automation";
import { createFakeBlockDocument } from "@/mocks/create-fake-block-document";
import { createFakeDeployment } from "@/mocks/create-fake-deployment";
import { createFakeFlow } from "@/mocks/create-fake-flow";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { createFakeWorkQueue } from "@/mocks/create-fake-work-queue";
import { EventResourceCombobox } from "./event-resource-combobox";

const MOCK_AUTOMATIONS = [
	createFakeAutomation({ id: "automation-1", name: "Test Automation 1" }),
	createFakeAutomation({ id: "automation-2", name: "Test Automation 2" }),
];

const MOCK_BLOCKS = [
	createFakeBlockDocument({ id: "block-1", name: "Test Block 1" }),
	createFakeBlockDocument({ id: "block-2", name: "Test Block 2" }),
];

const MOCK_DEPLOYMENTS = [
	createFakeDeployment({ id: "deployment-1", name: "Test Deployment 1" }),
	createFakeDeployment({ id: "deployment-2", name: "Test Deployment 2" }),
];

const MOCK_FLOWS = [
	createFakeFlow({ id: "flow-1", name: "Test Flow 1" }),
	createFakeFlow({ id: "flow-2", name: "Test Flow 2" }),
];

const MOCK_WORK_POOLS = [
	createFakeWorkPool({ name: "test-work-pool-1" }),
	createFakeWorkPool({ name: "test-work-pool-2" }),
];

const MOCK_WORK_QUEUES = [
	createFakeWorkQueue({ id: "work-queue-1", name: "Test Work Queue 1" }),
	createFakeWorkQueue({ id: "work-queue-2", name: "Test Work Queue 2" }),
];

const mockResourceAPIs = () => {
	server.use(
		http.post(buildApiUrl("/automations/filter"), () => {
			return HttpResponse.json(MOCK_AUTOMATIONS);
		}),
		http.post(buildApiUrl("/block_documents/filter"), () => {
			return HttpResponse.json(MOCK_BLOCKS);
		}),
		http.post(buildApiUrl("/deployments/filter"), () => {
			return HttpResponse.json(MOCK_DEPLOYMENTS);
		}),
		http.post(buildApiUrl("/flows/filter"), () => {
			return HttpResponse.json(MOCK_FLOWS);
		}),
		http.post(buildApiUrl("/work_pools/filter"), () => {
			return HttpResponse.json(MOCK_WORK_POOLS);
		}),
		http.post(buildApiUrl("/work_queues/filter"), () => {
			return HttpResponse.json(MOCK_WORK_QUEUES);
		}),
	);
};

beforeAll(() => {
	Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
		value: vi.fn(),
		configurable: true,
		writable: true,
	});
});

beforeEach(() => {
	mockResourceAPIs();
});

describe("EventResourceCombobox", () => {
	it("renders with empty message when no resources selected", async () => {
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("All resources")).toBeInTheDocument();
		});
	});

	it("renders with custom empty message", async () => {
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
				emptyMessage="Select resources"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("Select resources")).toBeInTheDocument();
		});
	});

	it("opens dropdown and shows search input", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByRole("combobox")).toBeInTheDocument();
			expect(
				screen.getByPlaceholderText("Search resources..."),
			).toBeInTheDocument();
		});
	});

	it("displays resources grouped by type", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByText("Automations")).toBeInTheDocument();
			expect(screen.getByText("Blocks")).toBeInTheDocument();
			expect(screen.getByText("Deployments")).toBeInTheDocument();
			expect(screen.getByText("Flows")).toBeInTheDocument();
			expect(screen.getByText("Work Pools")).toBeInTheDocument();
			expect(screen.getByText("Work Queues")).toBeInTheDocument();
		});
	});

	it("displays resource names from API", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: "Test Automation 1" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "Test Flow 1" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "Test Deployment 1" }),
			).toBeInTheDocument();
		});
	});

	it("filters options based on search", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "Automation");

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: "Test Automation 1" }),
			).toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "Test Flow 1" }),
			).not.toBeInTheDocument();
		});
	});

	it("shows custom option when search contains a dot and doesn't match existing options", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "prefect.custom.resource");

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: /Add.*prefect\.custom\.resource/ }),
			).toBeInTheDocument();
		});
	});

	it("does not show custom option when search doesn't contain a dot", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "customresource");

		await waitFor(() => {
			expect(
				screen.queryByRole("option", { name: /Add/ }),
			).not.toBeInTheDocument();
		});
	});

	it("calls onToggleResource when selecting a resource", async () => {
		const onToggleResource = vi.fn();
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={onToggleResource}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText("Test Automation 1");
		await user.click(option);

		expect(onToggleResource).toHaveBeenCalledWith(
			"prefect.automation.automation-1",
		);
	});

	it("calls onToggleResource when selecting a custom resource", async () => {
		const onToggleResource = vi.fn();
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={onToggleResource}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "prefect.my.custom");

		const listbox = await screen.findByRole("listbox");
		const customOption = await within(listbox).findByText(
			/Add.*prefect\.my\.custom/,
		);
		await user.click(customOption);

		expect(onToggleResource).toHaveBeenCalledWith("prefect.my.custom");
	});

	it("displays selected resources with names", async () => {
		render(
			<EventResourceCombobox
				selectedResourceIds={[
					"prefect.automation.automation-1",
					"prefect.flow.flow-1",
				]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(
				screen.getByText("Test Automation 1, Test Flow 1"),
			).toBeInTheDocument();
		});
	});

	it("displays selected resources with overflow indicator", async () => {
		render(
			<EventResourceCombobox
				selectedResourceIds={[
					"prefect.automation.automation-1",
					"prefect.flow.flow-1",
					"prefect.deployment.deployment-1",
				]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("+ 1")).toBeInTheDocument();
		});
	});

	it("displays resource ID when resource is not found", async () => {
		render(
			<EventResourceCombobox
				selectedResourceIds={["prefect.unknown.resource-id"]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(
				screen.getByText("prefect.unknown.resource-id"),
			).toBeInTheDocument();
		});
	});

	it("clears search after selecting a resource", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={[]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "Automation");

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText("Test Automation 1");
		await user.click(option);

		await waitFor(() => {
			expect(searchInput).toHaveValue("");
		});
	});

	it("shows check mark for selected resources", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={["prefect.automation.automation-1"]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			const selectedOption = screen.getByRole("option", {
				name: "Test Automation 1",
			});
			const checkIcon = selectedOption.querySelector("svg");
			expect(checkIcon).toHaveClass("opacity-100");
		});
	});

	it("does not show check mark for unselected resources", async () => {
		const user = userEvent.setup();
		render(
			<EventResourceCombobox
				selectedResourceIds={["prefect.automation.automation-1"]}
				onToggleResource={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			const unselectedOption = screen.getByRole("option", {
				name: "Test Automation 2",
			});
			const checkIcon = unselectedOption.querySelector("svg");
			expect(checkIcon).toHaveClass("opacity-0");
		});
	});
});
