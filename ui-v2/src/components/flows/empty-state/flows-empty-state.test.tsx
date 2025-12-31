import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FlowsEmptyState } from "./flows-empty-state";

describe("FlowsEmptyState", () => {
	it("renders the empty state with correct content", () => {
		render(<FlowsEmptyState />);

		expect(
			screen.getByRole("heading", { name: /run a flow to get started/i }),
		).toBeVisible();

		expect(
			screen.getByText(
				/flows are python functions that encapsulate workflow logic/i,
			),
		).toBeVisible();

		expect(screen.getByRole("link", { name: /view docs/i })).toBeVisible();
	});

	it("links to the flows documentation", () => {
		render(<FlowsEmptyState />);

		const docsLink = screen.getByRole("link", { name: /view docs/i });
		expect(docsLink).toHaveAttribute(
			"href",
			"https://docs.prefect.io/v3/develop/flows",
		);
	});
});
