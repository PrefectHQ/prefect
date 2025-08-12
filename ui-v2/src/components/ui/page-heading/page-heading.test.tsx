import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PageHeading } from "./page-heading";

describe("PageHeading", () => {
	it("renders title correctly", () => {
		render(<PageHeading title="Test Title" />);
		expect(screen.getByText("Test Title")).toBeInTheDocument();
	});

	it("renders subtitle when provided", () => {
		render(<PageHeading title="Test Title" subtitle="Test Subtitle" />);
		expect(screen.getByText("Test Subtitle")).toBeInTheDocument();
	});

	it("renders breadcrumbs when provided", () => {
		render(
			<PageHeading
				title="Test Title"
				breadcrumbs={<div>Test Breadcrumbs</div>}
			/>,
		);
		expect(screen.getByText("Test Breadcrumbs")).toBeInTheDocument();
	});

	it("renders actions when provided", () => {
		render(
			<PageHeading title="Test Title" actions={<button type="button">Test Action</button>} />,
		);
		expect(screen.getByText("Test Action")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<PageHeading title="Test Title" className="custom-class" />,
		);
		expect(container.querySelector(".custom-class")).toBeInTheDocument();
	});

	it("renders all components together", () => {
		render(
			<PageHeading
				title="Test Title"
				subtitle="Test Subtitle"
				breadcrumbs={<div>Test Breadcrumbs</div>}
				actions={<button type="button">Test Action</button>}
			/>,
		);
		expect(screen.getByText("Test Title")).toBeInTheDocument();
		expect(screen.getByText("Test Subtitle")).toBeInTheDocument();
		expect(screen.getByText("Test Breadcrumbs")).toBeInTheDocument();
		expect(screen.getByText("Test Action")).toBeInTheDocument();
	});
});
