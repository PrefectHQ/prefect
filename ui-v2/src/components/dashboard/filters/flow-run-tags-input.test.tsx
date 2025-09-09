import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { FlowRunTagsInput } from "./flow-run-tags-input";

// Mock the API
vi.mock("@/api/flow-run-tags", () => ({
	buildListFlowRunTagsQuery: () => ({
		queryKey: ["flowRunTags", "list"],
		queryFn: vi
			.fn()
			.mockResolvedValue(["tag1", "tag2", "tag3", "production", "development"]),
		staleTime: 5 * 60 * 1000,
		gcTime: 10 * 60 * 1000,
	}),
}));

const createTestQueryClient = () =>
	new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

const renderWithQueryClient = (component: React.ReactElement) => {
	const queryClient = createTestQueryClient();
	return render(
		<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
	);
};

describe("FlowRunTagsInput", () => {
	test("renders with placeholder when no tags selected", async () => {
		const onChange = vi.fn();

		renderWithQueryClient(
			<FlowRunTagsInput onChange={onChange} placeholder="Select tags" />,
		);

		await waitFor(() => {
			expect(screen.getByText("Select tags")).toBeInTheDocument();
		});
	});

	test("renders with selected tags count", async () => {
		const onChange = vi.fn();

		renderWithQueryClient(
			<FlowRunTagsInput value={["tag1", "tag2"]} onChange={onChange} />,
		);

		await waitFor(() => {
			expect(screen.getByText("2 tags selected")).toBeInTheDocument();
		});
	});

	test("renders with singular tag count", async () => {
		const onChange = vi.fn();

		renderWithQueryClient(
			<FlowRunTagsInput value={["tag1"]} onChange={onChange} />,
		);

		await waitFor(() => {
			expect(screen.getByText("1 tag selected")).toBeInTheDocument();
		});
	});

	test("displays selected tags as badges", async () => {
		const onChange = vi.fn();

		renderWithQueryClient(
			<FlowRunTagsInput
				value={["production", "critical"]}
				onChange={onChange}
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("production")).toBeInTheDocument();
			expect(screen.getByText("critical")).toBeInTheDocument();
		});
	});

	test("opens dropdown when trigger is clicked", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		renderWithQueryClient(<FlowRunTagsInput onChange={onChange} />);

		await waitFor(() => {
			expect(screen.getByText("Filter by tags")).toBeInTheDocument();
		});

		const trigger = screen.getByRole("button", { name: /select tags/i });
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search tags...")).toBeInTheDocument();
		});
	});

	test("filters available tags based on search input", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		renderWithQueryClient(<FlowRunTagsInput onChange={onChange} />);

		const trigger = screen.getByRole("button", { name: /select tags/i });
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search tags...")).toBeInTheDocument();
		});

		const searchInput = screen.getByPlaceholderText("Search tags...");
		await user.type(searchInput, "prod");

		await waitFor(() => {
			expect(screen.getByText("production")).toBeInTheDocument();
			expect(screen.queryByText("development")).not.toBeInTheDocument();
		});
	});

	test("adds tag when selected from dropdown", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		renderWithQueryClient(<FlowRunTagsInput value={[]} onChange={onChange} />);

		const trigger = screen.getByRole("button", { name: /select tags/i });
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByText("tag1")).toBeInTheDocument();
		});

		const tag1Option = screen.getByText("tag1");
		await user.click(tag1Option);

		expect(onChange).toHaveBeenCalledWith(["tag1"]);
	});

	test("does not add duplicate tags", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		renderWithQueryClient(
			<FlowRunTagsInput value={["tag1"]} onChange={onChange} />,
		);

		const trigger = screen.getByRole("button", { name: /select tags/i });
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByText("tag2")).toBeInTheDocument();
		});

		// tag1 should not be in the filtered options since it's already selected
		expect(screen.queryByText("tag1")).not.toBeInTheDocument();
	});

	test("removes tag when badge remove button is clicked", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		renderWithQueryClient(
			<FlowRunTagsInput
				value={["production", "staging"]}
				onChange={onChange}
			/>,
		);

		await waitFor(() => {
			expect(screen.getByText("production")).toBeInTheDocument();
		});

		// Find the remove button for 'production' tag
		const productionBadge = screen
			.getByText("production")
			.closest(".bg-secondary");
		const removeButton = productionBadge?.querySelector("button");
		expect(removeButton).toBeInTheDocument();

		if (removeButton) {
			await user.click(removeButton);
		}

		expect(onChange).toHaveBeenCalledWith(["staging"]);
	});

	test("allows creating new tags not in available options", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		renderWithQueryClient(<FlowRunTagsInput onChange={onChange} />);

		const trigger = screen.getByRole("button", { name: /select tags/i });
		await user.click(trigger);

		const searchInput = screen.getByPlaceholderText("Search tags...");
		await user.type(searchInput, "newtag");

		await waitFor(() => {
			expect(screen.getByText('Create "newtag"')).toBeInTheDocument();
		});

		const createOption = screen.getByText('Create "newtag"');
		await user.click(createOption);

		expect(onChange).toHaveBeenCalledWith(["newtag"]);
	});

	test("limits displayed tags to 10", async () => {
		const onChange = vi.fn();

		// Mock a large number of tags
		vi.mocked(
			require("@/api/flow-run-tags").buildListFlowRunTagsQuery,
		).mockReturnValue({
			queryKey: ["flowRunTags", "list"],
			queryFn: vi
				.fn()
				.mockResolvedValue(Array.from({ length: 20 }, (_, i) => `tag${i + 1}`)),
			staleTime: 5 * 60 * 1000,
			gcTime: 10 * 60 * 1000,
		});

		renderWithQueryClient(<FlowRunTagsInput onChange={onChange} />);

		const trigger = screen.getByRole("button", { name: /select tags/i });
		await userEvent.click(trigger);

		await waitFor(() => {
			// Should only show first 10 tags
			expect(screen.getByText("tag1")).toBeInTheDocument();
			expect(screen.getByText("tag10")).toBeInTheDocument();
			expect(screen.queryByText("tag11")).not.toBeInTheDocument();
		});
	});

	test("applies custom className", async () => {
		const onChange = vi.fn();

		const { container } = renderWithQueryClient(
			<FlowRunTagsInput onChange={onChange} className="custom-class" />,
		);

		await waitFor(() => {
			expect(container.firstChild).toHaveClass("custom-class");
		});
	});

	test("shows empty state when no tags available", async () => {
		const onChange = vi.fn();

		// Mock empty tags
		vi.mocked(
			require("@/api/flow-run-tags").buildListFlowRunTagsQuery,
		).mockReturnValue({
			queryKey: ["flowRunTags", "list"],
			queryFn: vi.fn().mockResolvedValue([]),
			staleTime: 5 * 60 * 1000,
			gcTime: 10 * 60 * 1000,
		});

		renderWithQueryClient(<FlowRunTagsInput onChange={onChange} />);

		const trigger = screen.getByRole("button", { name: /select tags/i });
		await userEvent.click(trigger);

		await waitFor(() => {
			expect(screen.getByText("No tags available.")).toBeInTheDocument();
		});
	});

	test("shows no results state when search yields no matches", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		renderWithQueryClient(<FlowRunTagsInput onChange={onChange} />);

		const trigger = screen.getByRole("button", { name: /select tags/i });
		await user.click(trigger);

		const searchInput = screen.getByPlaceholderText("Search tags...");
		await user.type(searchInput, "nonexistenttag");

		await waitFor(() => {
			expect(screen.getByText("No tags found.")).toBeInTheDocument();
		});
	});
});
