import { QueryClient } from "@tanstack/react-query";

import { AuthError } from "@/lib/api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => !(error instanceof AuthError) && failureCount < 1,
    },
  },
});
