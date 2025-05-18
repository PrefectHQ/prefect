import { useCreateWorkPool } from "@/api/work-pools";
import { WorkPoolForm, type WorkPoolFormValues } from "@/components/work-pools/work-pool-form";
import { createFileRoute } from "@tanstack/react-router";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

export const Route = createFileRoute("/work-pools/create")({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const { createWorkPool, isPending } = useCreateWorkPool();

  const onSubmit = (values: WorkPoolFormValues) => {
    createWorkPool(
      {
        name: values.name,
        description: values.description,
        type: values.type,
        concurrency_limit: values.concurrency_limit,
        is_paused: values.is_paused ?? false,
      },
      {
        onSuccess: () => {
          toast.success("Work pool created");
          navigate({ to: "/work-pools" });
        },
        onError: (err) => {
          const message = err.message ?? "Unknown error";
          toast.error(message);
        },
      },
    );
  };

  return <WorkPoolForm onSubmit={onSubmit} loading={isPending} />;
}
