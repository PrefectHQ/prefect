import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import { WorkPoolQueueRowActions } from "./work-pool-queue-row-actions";

// Mock the child components
vi.mock("@/components/work-pools/work-pool-queue-toggle", () => ({
	WorkPoolQueueToggle: vi.fn(
		({
			queue,
			onUpdate,
			className,
		}: {
			queue: { name: string };
			onUpdate?: () => void;
			className?: string;
		}) => (
			<div data-testid="work-pool-queue-toggle">
				<span>Queue: {queue.name}</span>
				{onUpdate && <span>Has onUpdate</span>}
				{className && <span>Class: {className}</span>}
			</div>
		),
	),
}));

vi.mock("@/components/work-pools/work-pool-queue-menu", () => ({
	WorkPoolQueueMenu: vi.fn(
		({
			queue,
			onUpdate,
			className,
		}: {
			queue: { name: string };
			onUpdate?: () => void;
			className?: string;
		}) => (
			<div data-testid="work-pool-queue-menu">
				<span>Queue: {queue.name}</span>
				{onUpdate && <span>Has onUpdate</span>}
				{className && <span>Class: {className}</span>}
			</div>
		),
	),
}));

describe("WorkPoolQueueRowActions", () => {
	const defaultQueue = createFakeWorkPoolQueue({
		name: "test-queue",
		work_pool_name: "test-pool",
	});

	it("renders both toggle and menu components", () => {
		render(<WorkPoolQueueRowActions queue={defaultQueue} />);

		expect(screen.getByTestId("work-pool-queue-toggle")).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-queue-menu")).toBeInTheDocument();
	});

	it("passes queue prop to both components", () => {
		render(<WorkPoolQueueRowActions queue={defaultQueue} />);

		const toggleComponent = screen.getByTestId("work-pool-queue-toggle");
		const menuComponent = screen.getByTestId("work-pool-queue-menu");

		expect(toggleComponent).toHaveTextContent("Queue: test-queue");
		expect(menuComponent).toHaveTextContent("Queue: test-queue");
	});

	it("passes onUpdate prop to both components when provided", () => {
		const onUpdate = vi.fn();
		render(
			<WorkPoolQueueRowActions queue={defaultQueue} onUpdate={onUpdate} />,
		);

		const toggleComponent = screen.getByTestId("work-pool-queue-toggle");
		const menuComponent = screen.getByTestId("work-pool-queue-menu");

		expect(toggleComponent).toHaveTextContent("Has onUpdate");
		expect(menuComponent).toHaveTextContent("Has onUpdate");
	});

	it("works without onUpdate prop", () => {
		render(<WorkPoolQueueRowActions queue={defaultQueue} />);

		const toggleComponent = screen.getByTestId("work-pool-queue-toggle");
		const menuComponent = screen.getByTestId("work-pool-queue-menu");

		expect(toggleComponent).not.toHaveTextContent("Has onUpdate");
		expect(menuComponent).not.toHaveTextContent("Has onUpdate");
	});

	it("has correct container structure and classes", () => {
		const { container } = render(
			<WorkPoolQueueRowActions queue={defaultQueue} />,
		);

		const wrapper = container.firstChild as HTMLElement;
		expect(wrapper).toHaveClass(
			"flex",
			"items-center",
			"justify-end",
			"space-x-2",
		);
	});

	it("renders components in correct order - toggle first, then menu", () => {
		render(<WorkPoolQueueRowActions queue={defaultQueue} />);

		const container = screen.getByTestId(
			"work-pool-queue-toggle",
		).parentElement;
		const children = Array.from(container?.children || []);

		expect(children[0]).toHaveAttribute(
			"data-testid",
			"work-pool-queue-toggle",
		);
		expect(children[1]).toHaveAttribute("data-testid", "work-pool-queue-menu");
	});

	it("handles different queue configurations", () => {
		const customQueue = createFakeWorkPoolQueue({
			name: "custom-queue-name",
			work_pool_name: "custom-pool",
		});

		render(<WorkPoolQueueRowActions queue={customQueue} />);

		const toggleComponent = screen.getByTestId("work-pool-queue-toggle");
		const menuComponent = screen.getByTestId("work-pool-queue-menu");

		expect(toggleComponent).toHaveTextContent("Queue: custom-queue-name");
		expect(menuComponent).toHaveTextContent("Queue: custom-queue-name");
	});

	it("calls onUpdate function properly", () => {
		const onUpdate = vi.fn();
		render(
			<WorkPoolQueueRowActions queue={defaultQueue} onUpdate={onUpdate} />,
		);

		// Verify that the onUpdate prop is passed to child components
		// The actual function behavior would be tested in the individual component tests
		expect(screen.getByTestId("work-pool-queue-toggle")).toHaveTextContent(
			"Has onUpdate",
		);
		expect(screen.getByTestId("work-pool-queue-menu")).toHaveTextContent(
			"Has onUpdate",
		);
	});
});
