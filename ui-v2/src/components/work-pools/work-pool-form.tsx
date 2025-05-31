import type { components } from "@/api/prefect";
import type { WorkPool } from "@/api/work-pools";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const formSchema = z.object({
  name: z.string().min(1, { message: "Name is required" }),
  description: z.string().optional(),
  type: z.string().min(1, { message: "Type is required" }),
  is_paused: z.boolean().optional(),
  concurrency_limit: z
    .preprocess(
      (val) => (val === "" || val === undefined || val === null ? undefined : Number(val)),
      z.number().optional(),
    ),
});

export type WorkPoolFormValues = z.infer<typeof formSchema>;

export type WorkPoolFormProps = {
  onSubmit: (values: WorkPoolFormValues) => void;
  workPool?: WorkPool;
  loading?: boolean;
};

export const WorkPoolForm = ({ onSubmit, workPool, loading }: WorkPoolFormProps) => {
  const form = useForm<WorkPoolFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      description: "",
      type: "prefect-agent",
      is_paused: false,
      concurrency_limit: undefined,
    },
  });

  useEffect(() => {
    if (workPool) {
      form.reset({
        name: workPool.name,
        description: workPool.description ?? "",
        type: workPool.type,
        is_paused: workPool.is_paused ?? false,
        concurrency_limit: workPool.concurrency_limit ?? undefined,
      });
    }
  }, [workPool, form]);

  return (
    <Form {...form}>
      <form onSubmit={(e) => void form.handleSubmit(onSubmit)(e)} className="space-y-4">
        <FormMessage>{form.formState.errors.root?.message}</FormMessage>
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input {...field} disabled={!!workPool} autoComplete="off" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Type</FormLabel>
              <FormControl>
                <Input {...field} disabled={!!workPool} autoComplete="off" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea {...field} className="min-h-20" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="concurrency_limit"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Concurrency Limit</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  value={field.value ?? ""}
                  onChange={(e) => field.onChange(e.target.value === "" ? undefined : Number(e.target.value))}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="is_paused"
          render={({ field }) => (
            <FormItem className="flex items-center gap-2">
              <FormControl>
                <Switch checked={field.value} onCheckedChange={field.onChange} />
              </FormControl>
              <FormLabel>Paused</FormLabel>
            </FormItem>
          )}
        />
        <div className="flex justify-end">
          <Button type="submit" loading={loading}>
            {workPool ? "Save" : "Create"}
          </Button>
        </div>
      </form>
    </Form>
  );
};

