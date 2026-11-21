import { fireEvent, render, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { DetailTable } from "./detail-table";

const sampleData =
	'[{"customer_id": "12345", "name": "John Smith", "churn_probability": 0.85}, {"customer_id": "56789", "name": "Jane Jones", "churn_probability": 0.65}]';

describe("ArtifactDetailTable", () => {
	it.each([{ name: "Alice" }, {}])(
		"renders columns from later rows when the first row is %j",
		(firstRow) => {
			const { getAllByRole } = render(
				<DetailTable
					tableData={JSON.stringify([
						firstRow,
						{ name: "Bob", result: "Passed" },
					])}
				/>,
			);

			expect(
				getAllByRole("columnheader").map((header) => header.textContent),
			).toEqual(["name", "result"]);
			const rows = getAllByRole("row");
			expect(
				within(rows[1])
					.getAllByRole("cell")
					.map((cell) => cell.textContent),
			).toEqual([firstRow.name ?? "", ""]);
			expect(
				within(rows[2])
					.getAllByRole("cell")
					.map((cell) => cell.textContent),
			).toEqual(["Bob", "Passed"]);
		},
	);

	it("renders artifact detail table", () => {
		const artifact = createFakeArtifact({
			type: "table",
			data: sampleData,
		});

		const { getByText } = render(
			<DetailTable tableData={artifact.data as string} />,
		);

		expect(getByText("customer_id")).toBeTruthy();
		expect(getByText("name")).toBeTruthy();
		expect(getByText("churn_probability")).toBeTruthy();
		expect(getByText("12345")).toBeTruthy();
		expect(getByText("John Smith")).toBeTruthy();
		expect(getByText("0.85")).toBeTruthy();
		expect(getByText("56789")).toBeTruthy();
		expect(getByText("Jane Jones")).toBeTruthy();
		expect(getByText("0.65")).toBeTruthy();
	});

	it("filters table data", async () => {
		const artifact = createFakeArtifact({
			type: "table",
			data: sampleData,
		});

		const { queryByPlaceholderText, getByText, queryByText } = render(
			<DetailTable tableData={artifact.data as string} />,
		);

		const searchInput = queryByPlaceholderText("Search");
		expect(searchInput).toBeTruthy();
		fireEvent.change(searchInput as HTMLInputElement, {
			target: { value: "12345" },
		});

		// expect Jane Jones to be filtered out
		await waitFor(() => {
			expect(getByText("12345")).toBeTruthy();
			expect(getByText("John Smith")).toBeTruthy();
			expect(queryByText("Jane Jones")).toBeFalsy();
		});
	});
});
