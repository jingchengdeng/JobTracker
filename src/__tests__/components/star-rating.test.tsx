import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StarRating } from "@/components/star-rating";

describe("StarRating", () => {
  it("renders 5 star buttons", () => {
    render(<StarRating value={0} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(5);
  });

  it("calls onChange with star number on click", () => {
    const onChange = vi.fn();
    render(<StarRating value={0} onChange={onChange} />);

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[2]); // click 3rd star

    expect(onChange).toHaveBeenCalledWith(3);
  });

  it("toggles off when clicking the current value", () => {
    const onChange = vi.fn();
    render(<StarRating value={3} onChange={onChange} />);

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[2]); // click 3rd star again

    expect(onChange).toHaveBeenCalledWith(0);
  });

  it("disables buttons in readonly mode", () => {
    render(<StarRating value={4} readonly />);
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("handles null value", () => {
    render(<StarRating value={null} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(5);
  });
});
