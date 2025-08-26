import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { LateFlowRunsIndicator } from "./late-flow-runs-indicator";

test("shows late flow runs count correctly", () => {
	render(<LateFlowRunsIndicator lateRunsCount={5} />);

	expect(screen.getByText("5")).toBeInTheDocument();
});

test("hides when no late flow runs", () => {
	const { container } = render(<LateFlowRunsIndicator lateRunsCount={0} />);

	expect(container.firstChild).toBeNull();
});

test("shows tooltip with appropriate message", async () => {
	const user = userEvent.setup();

	render(<LateFlowRunsIndicator lateRunsCount={3} />);

	const badge = screen.getByRole("button");
	await user.hover(badge);

	expect(screen.getAllByText("Late Flow Runs")).toHaveLength(2);
	expect(screen.getAllByText("3 flow runs running late")).toHaveLength(2);
});

test("shows singular message for single late run", async () => {
	const user = userEvent.setup();

	render(<LateFlowRunsIndicator lateRunsCount={1} />);

	const badge = screen.getByRole("button");
	await user.hover(badge);

	expect(screen.getAllByText("1 flow run running late")).toHaveLength(2);
});

test("applies custom className", () => {
	render(<LateFlowRunsIndicator lateRunsCount={2} className="custom-class" />);

	const badge = screen.getByRole("button").firstChild;
	expect(badge).toHaveClass("custom-class");
});
