import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";

import { TripPage } from "@/pages/TripPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<TripPage />} />
          <Route path="/trip/:id" element={<TripPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
