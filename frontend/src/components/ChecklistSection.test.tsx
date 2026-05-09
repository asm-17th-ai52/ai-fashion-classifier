import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ChecklistSection from "./ChecklistSection";
import type { Check } from "@/api/schemas";

const checks: Check[] = [
  {
    id: "A1",
    group: "dresscode",
    label: "신발 카테고리가 기대 범위에 포함",
    result: "fail",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["착용 신발: 로퍼", "기대 범위: 옥스퍼드"],
  },
  {
    id: "A2",
    group: "dresscode",
    label: "상의 카테고리가 기대 범위에 포함",
    result: "pass",
    applicable: true,
    is_blocker: false,
    evidence_facts: ["드레스 셔츠 적합"],
  },
  {
    id: "A5",
    group: "dresscode",
    label: "한겨울 외투 착용 여부",
    result: "not_applicable",
    applicable: false,
    is_blocker: true,
    evidence_facts: [],
  },
];

describe("ChecklistSection", () => {
  it("renders matrix group abbreviation", () => {
    render(<ChecklistSection checks={checks} />);
    // New design uses abbreviations in matrix header
    expect(screen.getByText("DRES")).toBeInTheDocument();
  });

  it("renders check IDs in matrix", () => {
    render(<ChecklistSection checks={checks} />);
    // Matrix cells show check IDs
    const a1Cells = screen.getAllByText("A1");
    expect(a1Cells.length).toBeGreaterThan(0);
  });

  it("shows pass status for pass checks", () => {
    render(<ChecklistSection checks={checks} />);
    const passLabel = screen.getByText("상의 카테고리가 기대 범위에 포함");
    const row = passLabel.closest("li");
    // Pass row shows "pass" text in accent-green
    const passSpan = row?.querySelector(".text-accent-green");
    expect(passSpan).toBeInTheDocument();
  });

  it("shows fail status for fail checks", () => {
    render(<ChecklistSection checks={checks} />);
    const failLabel = screen.getByText("신발 카테고리가 기대 범위에 포함");
    const row = failLabel.closest("li");
    // Fail row shows "fail" text in accent-red
    const failSpan = row?.querySelector(".text-accent-red");
    expect(failSpan).toBeInTheDocument();
  });

  it('shows "n/a" for not_applicable', () => {
    render(<ChecklistSection checks={checks} />);
    // New design uses "n/a" instead of "해당 없음"
    const naEls = screen.getAllByText("n/a");
    expect(naEls.length).toBeGreaterThan(0);
  });

  it("expands evidence_facts on fail item click", () => {
    render(<ChecklistSection checks={checks} />);
    const btn = screen.getByRole("button", {
      name: /신발 카테고리가 기대 범위에 포함/,
    });
    expect(screen.queryByText(/착용 신발: 로퍼/)).not.toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.getByText(/착용 신발: 로퍼/)).toBeInTheDocument();
  });

  it("overrides fail to pass when id is in flippedToPass", () => {
    render(<ChecklistSection checks={checks} flippedToPass={new Set(["A1"])} />);
    const item = screen.getByText("신발 카테고리가 기대 범위에 포함").closest("li");
    // Flipped row shows "pass*" in accent-green
    const greenSpan = item?.querySelector(".text-accent-green");
    expect(greenSpan).toBeInTheDocument();
  });
});
