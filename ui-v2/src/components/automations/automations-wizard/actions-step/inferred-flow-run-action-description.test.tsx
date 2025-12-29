import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InferredFlowRunActionDescription } from "./inferred-flow-run-action-description";

describe("InferredFlowRunActionDescription", () => {
	it("renders resume action description", () => {
		render(<InferredFlowRunActionDescription action="resume" />);
		expect(
			screen.getByText("Resume a flow run inferred from the triggering event"),
		).toBeVisible();
	});

	it("renders cancel action description", () => {
		render(<InferredFlowRunActionDescription action="cancel" />);
		expect(
			screen.getByText("Cancel a flow run inferred from the triggering event"),
		).toBeVisible();
	});

	it("renders suspend action description", () => {
		render(<InferredFlowRunActionDescription action="suspend" />);
		expect(
			screen.getByText("Suspend a flow run inferred from the triggering event"),
		).toBeVisible();
	});
});
