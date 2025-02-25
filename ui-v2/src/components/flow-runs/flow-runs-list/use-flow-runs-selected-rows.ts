import { useState } from "react";

export const useFlowRunsSelectedRows = (defaultValues?: Array<string>) => {
	const [selectedRows, setSelectedRows] = useState<Set<string>>(
		new Set(defaultValues),
	);

	const addRow = (id: string) =>
		setSelectedRows((curr) => new Set(curr).add(id));

	const removeRow = (id: string) =>
		setSelectedRows((curr) => {
			const newValue = new Set(curr);
			newValue.delete(id);
			return newValue;
		});

	const onSelectRow = (id: string, checked: boolean) => {
		if (checked) {
			addRow(id);
		} else {
			removeRow(id);
		}
	};

	const clearSet = () => setSelectedRows(new Set());

	const utils = {
		addRow,
		removeRow,
		onSelectRow,
		clearSet,
	};

	return [selectedRows, setSelectedRows, utils] as const;
};
