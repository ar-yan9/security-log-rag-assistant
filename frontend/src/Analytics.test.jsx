import React from "react";
import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Analytics from "./Analytics.jsx";
it("uses explicit filters and whole-corpus counts with source lines", async () => {
  global.fetch = vi
    .fn()
    .mockResolvedValue({
      ok: true,
      json: async () => ({
        matching_records: 1,
        corpus_records: 50,
        structured_records: 48,
        by_service: [{ value: "ssh", records: 1 }],
        by_outcome: [],
        by_source_ip: [],
        timeline: [
          {
            event_id: "A",
            source_line: 3,
            timestamp: null,
            text: "one record",
          },
        ],
        warning: "No top-k",
      }),
    });
  render(<Analytics />);
  fireEvent.change(screen.getByLabelText("Outcome"), {
    target: { value: "failure" },
  });
  fireEvent.click(screen.getByText("Summarize all records"));
  await screen.findByText("1 matching records / 50 total");
  expect(JSON.parse(fetch.mock.calls[0][1].body).outcome).toBe("failure");
  expect(screen.getByText("A · line 3")).toBeInTheDocument();
  expect(screen.getByText("Timestamp unknown")).toBeInTheDocument();
});
it("shows invalid filter errors without invented counts", async () => {
  global.fetch = vi
    .fn()
    .mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Invalid timestamp" }),
    });
  render(<Analytics />);
  fireEvent.click(screen.getByText("Summarize all records"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Invalid timestamp",
  );
  expect(screen.queryByText("Export analytics JSON")).toBeNull();
});
