import { render } from "@testing-library/react";
import type { RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SessionProvider } from "@/store/sessionContext";
import type { ReactElement, ReactNode } from "react";

function AllProviders({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter>
      <SessionProvider>{children}</SessionProvider>
    </MemoryRouter>
  );
}

export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

export { screen, fireEvent, waitFor, act } from "@testing-library/react";
export { userEvent } from "@testing-library/user-event";
