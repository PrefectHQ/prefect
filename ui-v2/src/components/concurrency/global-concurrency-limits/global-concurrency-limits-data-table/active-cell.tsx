import type { CellContext } from "@tanstack/react-table";
import { toast } from "sonner";
import {
	type GlobalConcurrencyLimit,
	useUpdateGlobalConcurrencyLimit,
} from "@/api/global-concurrency-limits";
import { Switch } from "@/components/ui/switch";

export const ActiveCell = (
	props: CellContext<GlobalConcurrencyLimit, boolean>,
) => {
	const { updateGlobalConcurrencyLimit } = useUpdateGlobalConcurrencyLimit();

	const handleCheckedChange = (checked: boolean, id: string) => {
		updateGlobalConcurrencyLimit(
			{
				id_or_name: id,
				active: checked,
			},
			{
				onSuccess: () => {
					toast.success("Concurrency limit updated");
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while updating active field.";
					console.error(message);
				},
			},
		);
	};

	const rowActive = props.getValue();
	const rowId = props.row.original.id;

	return (
		<Switch
			aria-label="toggle active"
			checked={rowActive}
			onCheckedChange={(checked) => handleCheckedChange(checked, rowId)}
		/>
	);
};
