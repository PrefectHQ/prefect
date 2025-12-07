import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FlowRunStateTypeEmpty } from "./flow-run-state-type-empty";

describe("FlowRunStateTypeEmpty", () => {
	it("renders empty state message for failed state type", () => {
		render(<FlowRunStateTypeEmpty stateTypes={["FAILED"]} />);

		expect(
			screen.getByText("You currently have 0 failed runs."),
		).toBeInTheDocument();
	});

	it("renders empty state message for multiple state types", () => {
		render(<FlowRunStateTypeEmpty stateTypes={["FAILED", "CRASHED"]} />);

		expect(
			screen.getByText("You currently have 0 failed or crashed runs."),
		).toBeInTheDocument();
	});

	it("renders empty state message for scheduled state type as late", () => {
		render(<FlowRunStateTypeEmpty stateTypes={["SCHEDULED"]} />);

		expect(
			screen.getByText("You currently have 0 late runs."),
		).toBeInTheDocument();
	});

	it("renders empty state message for running state types", () => {
		render(<FlowRunStateTypeEmpty stateTypes={["RUNNING", "PENDING"]} />);

		expect(
			screen.getByText("You currently have 0 running or pending runs."),
		).toBeInTheDocument();
	});
});
