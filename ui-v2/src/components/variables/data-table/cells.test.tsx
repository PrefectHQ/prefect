import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { components } from "@/api/prefect";
import type { CellContext } from "@/lib/tanstack-table";
import { ValueCell } from "./cells";

vi.mock("@/hooks/use-is-overflowing", () => ({
	useIsOverflowing: () => false,
}));

const props = (
	value: NonNullable<components["schemas"]["Variable"]["value"]>,
) =>
	({ getValue: () => value }) as CellContext<
		components["schemas"]["Variable"],
		NonNullable<components["schemas"]["Variable"]["value"]>
	>;

describe("ValueCell", () => {
	it.each([
		[0, "0"],
		[false, "false"],
		["", '""'],
	])("renders the JSON value %j", (value, expected) => {
		render(<ValueCell {...props(value)} />);

		expect(screen.getByText(expected)).toBeInTheDocument();
	});
});
