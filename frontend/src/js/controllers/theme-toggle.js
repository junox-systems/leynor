import { Controller } from "@hotwired/stimulus";

//! connects to data-controller="theme-toggle"
// Toggles `.dark` on <html>. Persists explicit user choices in localStorage;
// on first visit falls back to the OS preference without persisting it.
// https://stimulus.hotwired.dev/reference/lifecycle-callbacks
export default class extends Controller {
  static STORAGE_KEY = "theme";
  static DARK_CLASS = "dark";

  connect() {
    const dark =
      this.readStored() === "dark" ||
      (this.readStored() === null &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    this.setTheme(dark, { persist: false });
  }

  toggle() {
    const dark = !document.documentElement.classList.contains(
      this.constructor.DARK_CLASS,
    );
    this.setTheme(dark, { persist: true });
  }

  setTheme(dark, { persist }) {
    document.documentElement.classList.toggle(this.constructor.DARK_CLASS, dark);
    if (persist) {
      this.writeStored(dark ? "dark" : "light");
    }
    this.element.setAttribute("aria-pressed", String(dark));
  }

  // localStorage can throw (private mode, blocked storage) — fall back to OS.
  readStored() {
    try {
      return localStorage.getItem(this.constructor.STORAGE_KEY);
    } catch {
      return null;
    }
  }

  writeStored(value) {
    try {
      localStorage.setItem(this.constructor.STORAGE_KEY, value);
    } catch {
      // Persistence is best-effort; theme still applies for this page.
    }
  }
}
