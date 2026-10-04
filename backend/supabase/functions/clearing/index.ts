import { forward } from "../_shared/forward.ts";

Deno.serve((request) => forward(request, "clearing-run"));
