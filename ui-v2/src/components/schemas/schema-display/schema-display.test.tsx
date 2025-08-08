import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SchemaDisplay } from "./schema-display";

describe("SchemaDisplay", () => {
	it("renders different property types correctly", () => {
		const schema = {
			properties: {
				name: {
					type: "string",
					title: "Name",
					description: "The name of the item",
				},
				count: {
					type: "number",
					title: "Count",
				},
				enabled: {
					type: "boolean",
					title: "Enabled",
				},
			},
		};

		const data = {
			name: "Test Item",
			count: 42,
			enabled: true,
		};

		render(<SchemaDisplay schema={schema} data={data} />);

		expect(screen.getByText("Name")).toBeInTheDocument();
		expect(screen.getByText("The name of the item")).toBeInTheDocument();
		expect(screen.getByText("Test Item")).toBeInTheDocument();

		expect(screen.getByText("Count")).toBeInTheDocument();
		expect(screen.getByText("42")).toBeInTheDocument();

		expect(screen.getByText("Enabled")).toBeInTheDocument();
		expect(screen.getByText("true")).toBeInTheDocument();
	});

	it("handles nested objects", () => {
		const schema = {
			properties: {
				config: {
					type: "object",
					title: "Configuration",
					properties: {
						host: { type: "string" },
						port: { type: "number" },
					},
				},
			},
		};

		const data = {
			config: {
				host: "localhost",
				port: 3000,
			},
		};

		render(<SchemaDisplay schema={schema} data={data} />);

		expect(screen.getByText("Configuration")).toBeInTheDocument();
		expect(screen.getByText("{...} (2 properties)")).toBeInTheDocument();
	});

	it("shows default values when data is missing", () => {
		const schema = {
			properties: {
				name: {
					type: "string",
					title: "Name",
					default: "Default Name",
				},
				count: {
					type: "number",
					title: "Count",
					default: 0,
				},
			},
		};

		const data = {};

		render(<SchemaDisplay schema={schema} data={data} />);

		expect(screen.getByText("Default Name")).toBeInTheDocument();
		expect(screen.getByText("0")).toBeInTheDocument();
	});

	it("handles arrays", () => {
		const schema = {
			properties: {
				tags: {
					type: "array",
					title: "Tags",
					items: { type: "string" },
				},
			},
		};

		const data = {
			tags: ["tag1", "tag2", "tag3"],
		};

		render(<SchemaDisplay schema={schema} data={data} />);

		expect(screen.getByText("Tags")).toBeInTheDocument();
		expect(screen.getByText("[...] (3 items)")).toBeInTheDocument();
	});

	it("handles empty schema properties", () => {
		const schema = {
			properties: {},
		};

		const data = {};

		render(<SchemaDisplay schema={schema} data={data} />);

		expect(screen.getByText("No properties to display")).toBeInTheDocument();
	});

	it("handles missing schema properties", () => {
		const schema = {};

		const data = {};

		render(<SchemaDisplay schema={schema} data={data} />);

		expect(screen.getByText("No properties defined")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const schema = {
			properties: {
				name: { type: "string", title: "Name" },
			},
		};

		const data = { name: "Test" };

		const { container } = render(
			<SchemaDisplay schema={schema} data={data} className="custom-class" />,
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});
});
