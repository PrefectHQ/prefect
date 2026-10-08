import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { ArtifactDataView } from "./artifact-data-view";

const rows = [
	{ metric: "latency", value: 120 },
	{ metric: "throughput", value: 1500 },
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
});
