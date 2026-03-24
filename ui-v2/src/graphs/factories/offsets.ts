import type { MaybeGetter } from "@/graphs/models/utilities";
import { toValue } from "@/graphs/utilities";

type SetOffsetParameters = {
	axis: number;
	nodeId: string;
	offset: number;
};

type UpdateOffsetAxisParameters = {
	axis: number;
	nodeId: string;
};

type RemoveOffsetParameters = {
	axis: number;
	nodeId: string;
};

export type Offsets = Awaited<ReturnType<typeof offsetsFactory>>;

export type OffsetParameters = {
	gap?: MaybeGetter<number>;
	minimum?: MaybeGetter<number>;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function offsetsFactory({
	gap = 0,
	minimum = 0,
}: OffsetParameters = {}) {
	const offsets: Map<number, Map<string, number>> = new Map();

	function getOffset(axis: number): number {
		const values = offsets.get(axis) ?? [];
		const value = Math.max(...values.values(), toValue(minimum));
		const valueWithGap = value + toValue(gap);

		return valueWithGap;
	}

	function getTotalOffset(axis: number): number {
		let value = 0;

		for (let index = 0; index < axis; index++) {
			value += getOffset(index);
		}

		return value;
	}

	function getTotalValue(axis: number): number {
		return getTotalOffset(axis + 1) - toValue(gap);
	}

	function setOffset({ axis, nodeId, offset }: SetOffsetParameters): void {
		const value = offsets.get(axis) ?? new Map<string, number>();

		value.set(nodeId, offset);

		offsets.set(axis, value);
	}

	function updateNodeAxis({ axis, nodeId }: UpdateOffsetAxisParameters): void {
		let currentAxis: number | undefined;
		let currentOffset: number | undefined;

		for (const [axis, nodes] of offsets.entries()) {
			if (nodes.has(nodeId)) {
				currentAxis = axis;
				currentOffset = nodes.get(nodeId);
				break;
			}
		}

		if (
			currentAxis === axis ||
			currentAxis === undefined ||
			currentOffset === undefined
		) {
			return;
		}

		removeOffset({ axis: currentAxis, nodeId });
		setOffset({ axis, nodeId, offset: currentOffset });
	}

	function removeOffset({ axis, nodeId }: RemoveOffsetParameters): void {
		offsets.get(axis)?.delete(nodeId);
	}

	function clear(): void {
		offsets.clear();
	}

	return {
		getOffset,
		getTotalOffset,
		getTotalValue,
		setOffset,
		updateNodeAxis,
		removeOffset,
		clear,
	};
}
