import { render, screen } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { InfrastructureConfigurationStep } from "./infrastructure-configuration-step";
import type { WorkPoolFormValues } from "./schema";

function TestWrapper({
	children,
	defaultValues = {},
}: {
	children: React.ReactNode;
	defaultValues?: Partial<WorkPoolFormValues>;
}) {
	const form = useForm<WorkPoolFormValues>({
		defaultValues,
	});

	return <FormProvider {...form}>{children}</FormProvider>;
}

describe("InfrastructureConfigurationStep", () => {
	it("renders infrastructure configuration with informational text", () => {
		render(
			<TestWrapper defaultValues={{ type: "kubernetes" }}>
				<InfrastructureConfigurationStep />
			</TestWrapper>,
		);

		expect(
			screen.getByText(/The fields below control the default values/),
		).toBeInTheDocument();
		expect(screen.getByText("Base Job Template")).toBeInTheDocument();
	});

	it("renders base job template form when no type is selected", () => {
		render(
			<TestWrapper>
				<InfrastructureConfigurationStep />
			</TestWrapper>,
		);

		expect(
			screen.getByText(/The fields below control the default values/),
		).toBeInTheDocument();
		expect(screen.getByText("Base Job Template")).toBeInTheDocument();
	});

	it("renders correctly with empty form values", () => {
		render(
			<TestWrapper defaultValues={{}}>
				<InfrastructureConfigurationStep />
			</TestWrapper>,
		);

		expect(screen.getByText("Base Job Template")).toBeInTheDocument();
	});

	it("renders correctly with different work pool types", () => {
		render(
			<TestWrapper defaultValues={{ type: "docker" }}>
				<InfrastructureConfigurationStep />
			</TestWrapper>,
		);

		expect(
			screen.getByText(/The fields below control the default values/),
		).toBeInTheDocument();
		expect(screen.getByText("Base Job Template")).toBeInTheDocument();
	});
});
