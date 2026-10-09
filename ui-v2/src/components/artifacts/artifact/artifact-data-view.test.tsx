import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { ArtifactDataView } from "./artifact-data-view";

const rows = [
	{ metric: "latency", value: 120 },
	{ metric: "throughput", value: 1500 },
];

const listRows = [
	["latency", 120],
	["throughput", 1500],
];

describe("ArtifactDataView", () => {
	it("renders markdown artifacts as markdown", async () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({
					type: "markdown",
					data: "# Daily report",
				})}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(
			await screen.findByRole("heading", { name: "Daily report" }),
		).toBeInTheDocument();
	});

	it("renders table artifacts with JSON string data", () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({
					type: "table",
					data: JSON.stringify(rows),
				})}
			/>,
		);

		expect(screen.getByText("metric")).toBeInTheDocument();
		expect(screen.getByText("latency")).toBeInTheDocument();
		expect(screen.getByText("1500")).toBeInTheDocument();
	});

	it("renders table artifacts with array data", () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({ type: "table", data: rows })}
			/>,
		);

		expect(screen.getByText("metric")).toBeInTheDocument();
		expect(screen.getByText("throughput")).toBeInTheDocument();
	});

	it("falls back for table artifacts with malformed JSON", () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({ type: "table", data: "not json" })}
				fallback={<p>fallback content</p>}
			/>,
		);

		expect(screen.getByText("fallback content")).toBeInTheDocument();
	});

	it("falls back for column-oriented table data", () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({
					type: "table",
					data: JSON.stringify({ metric: ["latency"], value: [120] }),
				})}
				fallback={<p>fallback content</p>}
			/>,
		);

		expect(screen.getByText("fallback content")).toBeInTheDocument();
	});

	it("renders progress artifacts", () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({ type: "progress", data: 42 })}
			/>,
		);

		expect(screen.getByText(/42/)).toBeInTheDocument();
	});

	it("renders unknown artifact types as JSON by default", () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({
					type: "result",
					data: { value: 42 },
				})}
			/>,
		);

		expect(screen.getByText(/"value": 42/)).toBeInTheDocument();
	});

	it("renders the fallback for unknown artifact types", () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({ type: "result", data: { value: 42 } })}
				fallback={<p>fallback content</p>}
			/>,
		);

		expect(screen.getByText("fallback content")).toBeInTheDocument();
	});

	it.each([
		["JSON string", JSON.stringify(listRows)],
		["array", listRows],
	])("renders list-of-lists table artifacts with %s data", (_, data) => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({ type: "table", data })}
				fallback={<p>fallback content</p>}
			/>,
		);

		expect(screen.getByRole("cell", { name: "latency" })).toBeInTheDocument();
		expect(screen.getByRole("cell", { name: "1500" })).toBeInTheDocument();
		expect(screen.queryByText("fallback content")).not.toBeInTheDocument();
	});

	it("filters list-of-lists table rows by search", async () => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({
					type: "table",
					data: JSON.stringify(listRows),
				})}
			/>,
		);

		fireEvent.change(screen.getByPlaceholderText("Search"), {
			target: { value: "through" },
		});

		await waitFor(() => {
			expect(
				screen.queryByRole("cell", { name: "latency" }),
			).not.toBeInTheDocument();
		});
		expect(
			screen.getByRole("cell", { name: "throughput" }),
		).toBeInTheDocument();
	});

	it.each([
		["null rows", [null]],
		["primitive rows", [1, 2]],
	])("falls back for table artifacts with %s", (_, data) => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({ type: "table", data })}
				fallback={<p>fallback content</p>}
			/>,
		);

		expect(screen.getByText("fallback content")).toBeInTheDocument();
	});

	it.each([
		["markdown", { not: "a string" }],
		["link", 42],
		["image", ["not", "a", "url"]],
		["progress", "50"],
	])("falls back for %s artifacts with unexpected data", (type, data) => {
		render(
			<ArtifactDataView
				artifact={createFakeArtifact({ type, data })}
				fallback={<p>fallback content</p>}
			/>,
		);

		expect(screen.getByText("fallback content")).toBeInTheDocument();
	});
});
