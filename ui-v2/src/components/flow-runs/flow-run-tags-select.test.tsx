import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import {
	afterAll,
	afterEach,
	beforeAll,
	describe,
	expect,
	it,
	vi,
} from "vitest";
import { FlowRunTagsSelect } from "./flow-run-tags-select";

// MSW server to mock API endpoints
const server = setupServer(
	http.post("/api/flow_runs/paginate", () => {
		return HttpResponse.json({
			results: [
				{ id: "1", tags: ["alpha", "prod"] },
				{ id: "2", tags: ["beta", "prod"] },
				{ id: "3", tags: [] },
			],
			pages: 1,
			next: null,
		});
	}),
);

beforeAll(() => {
	// Ensure the client builds requests against the MSW base URL
	vi.stubEnv("VITE_API_URL", "/api");
	// Polyfill scrollIntoView used by cmdk
	Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
		value: vi.fn(),
		configurable: true,
		writable: true,
	});
	server.listen();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWithQueryClient(ui: React.ReactElement) {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
	});
	return render(
		<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
	);
}

describe("FlowRunTagsSelect", () => {
	it("shows placeholder when no tags selected", () => {
		renderWithQueryClient(
			<FlowRunTagsSelect
				value={[]}
				onChange={vi.fn()}
				placeholder="All tags"
			/>,
		);
		// The trigger shows the placeholder text
		expect(screen.getByText("All tags")).toBeInTheDocument();
	});

	it("shows selected tags in the trigger", () => {
		renderWithQueryClient(
			<FlowRunTagsSelect value={["alpha", "beta"]} onChange={vi.fn()} />,
		);
		// Without opening dropdown, tags are visible in trigger
		expect(screen.getByText("alpha")).toBeInTheDocument();
		expect(screen.getByText("beta")).toBeInTheDocument();
	});

	// Suggestion rendering is covered implicitly by other integration tests; core interactions below

	it("adds a freeform tag on Enter", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		renderWithQueryClient(<FlowRunTagsSelect value={[]} onChange={onChange} />);

		const trigger = screen.getByRole("button", { name: /flow run tags/i });
		await user.click(trigger);

		const combo = screen.getByRole("combobox");
		await user.type(combo, "newtag");
		await user.keyboard("{Enter}");

		expect(onChange).toHaveBeenCalledWith(["newtag"]);
	});

	it("adds a tag when typing a trailing comma", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		renderWithQueryClient(<FlowRunTagsSelect value={[]} onChange={onChange} />);

		const trigger = screen.getByRole("button", { name: /flow run tags/i });
		await user.click(trigger);

		const input2 = screen.getByRole("combobox");
		await user.type(input2, "temp,");

		// Comma commits the tag and clears input; we expect onChange invoked
		await waitFor(() => {
			expect(onChange).toHaveBeenCalledWith(["temp"]);
		});
	});

	it("removes last tag on Backspace when input empty", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		// Start with one selected tag
		renderWithQueryClient(
			<FlowRunTagsSelect value={["alpha"]} onChange={onChange} />,
		);

		const trigger = screen.getByRole("button", { name: /flow run tags/i });
		await user.click(trigger);

		await user.keyboard("{Backspace}");

		expect(onChange).toHaveBeenCalledWith([]);
	});

	it("removes a tag via dropdown remove button", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		renderWithQueryClient(
			<FlowRunTagsSelect value={["alpha", "beta"]} onChange={onChange} />,
		);

		// Open and remove 'alpha' via dropdown
		const trigger = screen.getByRole("button", { name: /flow run tags/i });
		await user.click(trigger);
		const removeAlpha = await screen.findByRole("button", {
			name: /remove alpha tag/i,
		});
		await user.click(removeAlpha);

		expect(onChange).toHaveBeenCalledWith(["beta"]);
	});

	it("clears all tags via clear action", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		renderWithQueryClient(
			<FlowRunTagsSelect value={["alpha", "beta"]} onChange={onChange} />,
		);

		const trigger = screen.getByRole("button", { name: /flow run tags/i });
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		// Clear all item should be visible regardless of suggestions
		const clearItem = await within(listbox).findByText(/clear all tags/i);
		await user.click(clearItem);

		expect(onChange).toHaveBeenCalledWith([]);
	});

	it("does not show 'No tags found' when API returns no tags", async () => {
		// Return empty results
		server.use(
			http.post("/api/flow_runs/paginate", () =>
				HttpResponse.json({ results: [], pages: 0, next: null }),
			),
		);

		const user = userEvent.setup();
		renderWithQueryClient(<FlowRunTagsSelect value={[]} onChange={vi.fn()} />);

		const trigger = screen.getByRole("button", { name: /flow run tags/i });
		await user.click(trigger);

		// There is a listbox but no empty message
		const listbox = await screen.findByRole("listbox");
		expect(
			within(listbox).queryByText(/no tags found/i),
		).not.toBeInTheDocument();
	});
});
