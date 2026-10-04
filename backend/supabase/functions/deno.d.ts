// Type definitions for Supabase Edge Functions (Deno runtime) in VS Code
declare namespace Deno {
  export function serve(handler: (request: Request) => Response | Promise<Response>): void;
  export const env: {
    get(key: string): string | undefined;
  };
}
