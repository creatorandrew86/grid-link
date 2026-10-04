import { forward } from "../_shared/forward.ts";

Deno.serve((request: Request) => forward(request, "clearing-run"));
