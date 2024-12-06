import { useListGlobalConcurrencyLimits } from "@/hooks/global-concurrency-limits";
import { useState } from "react";

import { GlobalConcurrencyLimitsHeader } from "./global-concurrency-limits-header";

export const GlobalConcurrencyView = () => {
	const [showAddDialog, setShowAddDialog] = useState(false);

	const { data } = useListGlobalConcurrencyLimits();

	const openAddDialog = () => setShowAddDialog(true);
	const closeAddDialog = () => setShowAddDialog(false);

	return (
		<>
			<div className="flex flex-col gap-2">
				<GlobalConcurrencyLimitsHeader onAdd={openAddDialog} />
			</div>
			<div>TODO</div>
			<ul>
				{data.map((limit) => (
					<li key={limit.id}>{JSON.stringify(limit)}</li>
				))}
			</ul>
			{showAddDialog && <div onClick={closeAddDialog}>TODO: DIALOG</div>}
		</>
	);
};
