import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import {
	createFakeAutomation,
	createFakeBlockDocument,
	createFakeDeployment,
	createFakeFlow,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { EventsResourceFilter } from "./events-resource-filter";

const MOCK_AUTOMATION = createFakeAutomation({
	id: "automation-1",
	name: "Test Automation",
});
const MOCK_BLOCK = createFakeBlockDocument({
	id: "block-1",
	name: "Test Block",
});
const MOCK_DEPLOYMENT = createFakeDeployment({
	id: "deployment-1",
	name: "Test Deployment",
});
const MOCK_FLOW = createFakeFlow({
	id: "flow-1",
	name: "Test Flow",
});
const MOCK_WORK_POOL = createFakeWorkPool({
	id: "work-pool-uuid-1",
	name: "test-work-pool",
});
const MOCK_WORK_QUEUE = createFakeWorkQueue({
	id: "work-queue-1",
	name: "Test Work Queue",
});

const mockResourcesAPI = () => {
	server.use(
		http.post(buildApiUrl("/automations/filter"), () => {
			return HttpResponse.json([MOCK_AUTOMATION]);
		}),
		http.post(buildApiUrl("/block_documents/filter"), () => {
			return HttpResponse.json([MOCK_BLOCK]);
		}),
		http.post(buildApiUrl("/deployments/filter"), () => {
			return HttpResponse.json([MOCK_DEPLOYMENT]);
		}),
		http.post(buildApiUrl("/flows/filter"), () => {
			return HttpResponse.json([MOCK_FLOW]);
		}),
		http.post(buildApiUrl("/work_pools/filter"), () => {
			return HttpResponse.json([MOCK_WORK_POOL]);
		}),
		http.post(buildApiUrl("/work_queues/filter"), () => {
			return HttpResponse.json([MOCK_WORK_QUEUE]);
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
	mockResourcesAPI();
});

describe("EventsResourceFilter", () => {
	it("shows 'All resources' when no resources are selected", async () => {
		render(
			<EventsResourceFilter
				selectedResourceIds={[]}
				onResourceIdsChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("All resources")).toBeInTheDocument();
		});
	});

	it("shows count text when resources are selected", async () => {
		render(
			<EventsResourceFilter
				selectedResourceIds={[
					"prefect.automation.automation-1",
					"prefect.flow.flow-1",
				]}
				onResourceIdsChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("2 resources selected")).toBeInTheDocument();
		});
	});

	it("opens dropdown and shows grouped resources", async () => {
		const user = userEvent.setup();
		render(
			<EventsResourceFilter
				selectedResourceIds={[]}
				onResourceIdsChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by resource/i,
		});
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByText("Automation")).toBeInTheDocument();
			expect(screen.getByText("Flow")).toBeInTheDocument();
			expect(screen.getByText("Deployment")).toBeInTheDocument();
			expect(screen.getByText("Block")).toBeInTheDocument();
			expect(screen.getByText("Work Pool")).toBeInTheDocument();
			expect(screen.getByText("Work Queue")).toBeInTheDocument();
		});
	});

	it("selects a resource when clicking on it", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsResourceFilter
				selectedResourceIds={[]}
				onResourceIdsChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by resource/i,
		});
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const flowOption = await within(listbox).findByText("Test Flow");
		await user.click(flowOption);

		expect(onChange).toHaveBeenCalledWith(["prefect.flow.flow-1"]);
	});

	it("deselects a resource when clicking on an already selected item", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsResourceFilter
				selectedResourceIds={["prefect.flow.flow-1"]}
				onResourceIdsChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by resource/i,
		});
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const flowOption = await within(listbox).findByText("Test Flow");
		await user.click(flowOption);

		expect(onChange).toHaveBeenCalledWith([]);
	});

	it("filters resources by search input", async () => {
		const user = userEvent.setup();
		render(
			<EventsResourceFilter
				selectedResourceIds={[]}
				onResourceIdsChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by resource/i,
		});
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "Flow");

		await waitFor(() => {
			expect(screen.getByText("Test Flow")).toBeInTheDocument();
			expect(screen.queryByText("Test Automation")).not.toBeInTheDocument();
		});
	});

	it("shows 'No resources found' when search has no matches", async () => {
		const user = userEvent.setup();
		render(
			<EventsResourceFilter
				selectedResourceIds={[]}
				onResourceIdsChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by resource/i,
		});
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "nonexistent");

		await waitFor(() => {
			expect(screen.getByText("No resources found")).toBeInTheDocument();
		});
	});

	it("allows selecting multiple resources", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsResourceFilter
				selectedResourceIds={["prefect.flow.flow-1"]}
				onResourceIdsChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by resource/i,
		});
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const automationOption =
			await within(listbox).findByText("Test Automation");
		await user.click(automationOption);

		expect(onChange).toHaveBeenCalledWith([
			"prefect.flow.flow-1",
			"prefect.automation.automation-1",
		]);
	});
});
