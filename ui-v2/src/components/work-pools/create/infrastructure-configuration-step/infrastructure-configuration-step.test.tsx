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
	it("renders prefect agent message when work pool type is prefect-agent", () => {
		render(
			<TestWrapper defaultValues={{ type: "prefect-agent" }}>
				<InfrastructureConfigurationStep />
			</TestWrapper>,
		);

		expect(
			screen.getByText(
				/Prefect Agent work pools don't require infrastructure configuration/,
			),
		).toBeInTheDocument();
		expect(screen.queryByText("Base Job Template")).not.toBeInTheDocument();
	});

	it("renders base job template form for non-prefect-agent types", () => {
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
});
