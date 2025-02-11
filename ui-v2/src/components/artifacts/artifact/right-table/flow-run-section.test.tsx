import { createFakeFlowRun, createFakeState } from "@/mocks";
import { formatDate } from "@/utils/date";
import { faker } from "@faker-js/faker";
import { render } from "@testing-library/react";
import humanizeDuration from "humanize-duration";
import { describe, expect, it } from "vitest";
import { FlowRunSection } from "./flow-run-section";

describe("flow run section in details page right table", () => {
	const fakeFlowRun = createFakeFlowRun({
		tags: ["tag1", "tag2"],
	});

	it("renders flow run section with start time", () => {
		const { getByText } = render(
			<FlowRunSection flowRun={fakeFlowRun} showHr />,
		);

		expect(getByText("Start time")).toBeTruthy();
		expect(
			getByText(formatDate(fakeFlowRun.start_time ?? "", "dateTime")),
		).toBeTruthy();
	});

	it("renders flow run section with duration", () => {
		const { getByText } = render(
			<FlowRunSection flowRun={fakeFlowRun} showHr />,
		);

		expect(getByText("Duration")).toBeTruthy();
		expect(
			getByText(
				humanizeDuration(Math.ceil(fakeFlowRun.estimated_run_time) * 1000),
			),
		).toBeTruthy();
	});

	it("renders flow run section with created", () => {
		const { getByText } = render(
			<FlowRunSection flowRun={fakeFlowRun} showHr />,
		);

		expect(getByText("Created")).toBeTruthy();
		expect(
			getByText(formatDate(fakeFlowRun.created ?? "", "dateTime")),
		).toBeTruthy();
	});

	it("renders flow run section with last updated", () => {
		const { getByText } = render(
			<FlowRunSection flowRun={fakeFlowRun} showHr />,
		);

		expect(getByText("Last Updated")).toBeTruthy();
		expect(
			getByText(formatDate(fakeFlowRun.updated ?? "", "dateTime")),
		).toBeTruthy();
	});

	it("renders flow run section with tags", () => {
		const { getByText } = render(
			<FlowRunSection flowRun={fakeFlowRun} showHr />,
		);

		expect(getByText("Tags")).toBeTruthy();
		expect(getByText("tag1")).toBeTruthy();
		expect(getByText("tag2")).toBeTruthy();
	});

	it("renders flow run section with no tags", () => {
		const fakeFlowRunNoTags = createFakeFlowRun({
			tags: [],
		});
		const { getByText } = render(
			<FlowRunSection flowRun={fakeFlowRunNoTags} showHr />,
		);

		expect(getByText("Tags")).toBeTruthy();
		expect(getByText("None")).toBeTruthy();
	});

	it("renders flow run section with state message", () => {
		const { stateType, stateName } = createFakeState();
		const fakeFlowRunWithStateMessage = createFakeFlowRun({
			state: {
				id: faker.string.uuid(),
				type: stateType,
				name: stateName,
				timestamp: faker.date.past().toISOString(),
				message: "hello world",
				data: null,
				state_details: {
					flow_run_id: faker.string.uuid(),
					task_run_id: faker.string.uuid(),
					child_flow_run_id: null,
					scheduled_time: null,
					cache_key: null,
					cache_expiration: null,
					deferred: false,
					untrackable_result: false,
					pause_timeout: null,
					pause_reschedule: false,
					pause_key: null,
					run_input_keyset: null,
					refresh_cache: null,
					retriable: null,
					transition_id: null,
					task_parameters_id: null,
				},
			},
		});

		const { getByText } = render(
			<FlowRunSection flowRun={fakeFlowRunWithStateMessage} showHr />,
		);

		expect(getByText("State Message")).toBeTruthy();
		expect(
			getByText(fakeFlowRunWithStateMessage.state?.message ?? ""),
		).toBeTruthy();
	});
});
