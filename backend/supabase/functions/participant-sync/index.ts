import { forward } from "../_shared/forward.ts";

// Accepts the same participant payload as /api/signup; backend validates it.
Deno.serve((request: Request) => forward(request, "signup", true));
