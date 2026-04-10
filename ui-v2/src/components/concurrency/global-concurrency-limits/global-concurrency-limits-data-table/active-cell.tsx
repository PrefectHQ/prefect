import type { CellContext } from "@tanstack/react-table";
import { toast } from "sonner";
import {
	type GlobalConcurrencyLimit,
	useUpdateGlobalConcurrencyLimit,
} from "@/api/global-concurrency-limits";
import { Switch } from "@/components/ui/switch";

type ActiveCellProps = CellContext<GlobalConcurrencyLimit, unknown> & {
	canUpdate?: boolean;
};

export const ActiveCell = ({ canUpdate = true, ...props }: ActiveCellProps) => {
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

	const rowActive = props.row.original.active;
	const rowId = props.row.original.id;

	return (
		<Switch
			aria-label="toggle active"
			checked={rowActive}
			disabled={!canUpdate}
			onCheckedChange={(checked) => handleCheckedChange(checked, rowId)}
		/>
	);
};
