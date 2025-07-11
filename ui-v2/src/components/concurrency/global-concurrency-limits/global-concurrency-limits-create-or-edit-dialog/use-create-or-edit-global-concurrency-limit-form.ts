import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import {
	type GlobalConcurrencyLimit,
	useCreateGlobalConcurrencyLimit,
	useUpdateGlobalConcurrencyLimit,
} from "@/api/global-concurrency-limits";

const formSchema = z.object({
	active: z.boolean().default(true),
	/** Coerce to solve common issue of transforming a string number to a number type */
	denied_slots: z.number().default(0).or(z.string()).pipe(z.coerce.number()),
	/** Coerce to solve common issue of transforming a string number to a number type */
	limit: z.number().default(0).or(z.string()).pipe(z.coerce.number()),
	name: z
		.string()
		.min(2, { message: "Name must be at least 2 characters" })
		.default(""),
	/** Coerce to solve common issue of transforming a string number to a number type */
	slot_decay_per_second: z
		.number()
		.default(0)
		.or(z.string())
		.pipe(z.coerce.number()),
	/** Additional fields post creation. Coerce to solve common issue of transforming a string number to a number type  */
	active_slots: z.number().default(0).or(z.string()).pipe(z.coerce.number()),
});

const DEFAULT_VALUES = {
	active: true,
	name: "",
	limit: 0,
	slot_decay_per_second: 0,
	denied_slots: 0,
	active_slots: 0,
} as const;

type UseCreateOrEditGlobalConcurrencyLimitFormOptions = {
	/** Limit to edit. Pass undefined if creating a new limit */
	limitToUpdate: GlobalConcurrencyLimit | undefined;
	/** Callback after hitting Save or Update */
	onSubmit: () => void;
};

export const useCreateOrEditGlobalConcurrencyLimitForm = ({
	limitToUpdate,
	onSubmit,
}: UseCreateOrEditGlobalConcurrencyLimitFormOptions) => {
	const { createGlobalConcurrencyLimit, status: createStatus } =
		useCreateGlobalConcurrencyLimit();
	const { updateGlobalConcurrencyLimit, status: updateStatus } =
		useUpdateGlobalConcurrencyLimit();

	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: DEFAULT_VALUES,
	});

	// Sync form data with limit-to-edit data
	useEffect(() => {
		if (limitToUpdate) {
			const { active, name, limit, slot_decay_per_second, active_slots } =
				limitToUpdate;
			form.reset({ active, name, limit, slot_decay_per_second, active_slots });
		} else {
			form.reset(DEFAULT_VALUES);
		}
	}, [form, limitToUpdate]);

	const saveOrUpdate = (values: z.infer<typeof formSchema>) => {
		const onSettled = () => {
			form.reset(DEFAULT_VALUES);
			onSubmit();
		};

		if (limitToUpdate?.id) {
			updateGlobalConcurrencyLimit(
				{
					id_or_name: limitToUpdate.id,
					...values,
				},
				{
					onSuccess: () => {
						toast.success("Limit updated");
					},
					onError: (error) => {
						const message =
							error.message || "Unknown error while updating limit.";
						form.setError("root", { message });
					},
					onSettled,
				},
			);
		} else {
			createGlobalConcurrencyLimit(values, {
				onSuccess: () => {
					toast.success("Limit created");
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while creating variable.";
					form.setError("root", {
						message,
					});
				},
				onSettled,
			});
		}
	};

	return {
		form,
		saveOrUpdate,
		isLoading: createStatus === "pending" || updateStatus === "pending",
	};
};
