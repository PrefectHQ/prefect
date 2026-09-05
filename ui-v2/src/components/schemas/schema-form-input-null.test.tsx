import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { SchemaFormInputNull } from "./schema-form-input-null";

describe("SchemaFormInputNull", () => {
	test("reports null when the value is not already null", async () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputNull value={undefined} onValueChange={onValueChange} />,
		);

		expect(screen.getByText('Property is type "None"')).toBeInTheDocument();

		await waitFor(() => {
			expect(onValueChange).toHaveBeenCalledWith(null);
		});
	});

	test("does not report a value when the value is already null", () => {
		const onValueChange = vi.fn();

		render(<SchemaFormInputNull value={null} onValueChange={onValueChange} />);

		expect(onValueChange).not.toHaveBeenCalled();
	});
});
