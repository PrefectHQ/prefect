import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { SideDetails } from "./side-details";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-02T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: ["id-1", "id-2"],
};

test("SideDetails renders and parses data properly", () => {
	render(<SideDetails data={MOCK_DATA} />);
	expect(screen.getByText("my tag 0")).toBeVisible();
});
