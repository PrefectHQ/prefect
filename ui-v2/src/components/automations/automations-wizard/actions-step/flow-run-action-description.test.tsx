import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FlowRunActionDescription } from "./flow-run-action-description";

describe("FlowRunActionDescription", () => {
	it("renders suspend action description", () => {
		render(<FlowRunActionDescription action="Suspend" />);
		expect(
			screen.getByText("Suspend flow run inferred from the triggering event"),
		).toBeVisible();
	});

	it("renders cancel action description", () => {
		render(<FlowRunActionDescription action="Cancel" />);
		expect(
			screen.getByText("Cancel flow run inferred from the triggering event"),
		).toBeVisible();
	});

	it("renders resume action description", () => {
		render(<FlowRunActionDescription action="Resume" />);
		expect(
			screen.getByText("Resume a flow run inferred from the triggering event"),
		).toBeVisible();
	});
});
