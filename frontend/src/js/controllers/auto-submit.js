import { Controller } from "@hotwired/stimulus";

//! connects to data-controller="auto-submit"
// Submits the form when a control changes, skipping no-op changes (re-picking
// the current value) so the page doesn't reload for nothing.
export default class extends Controller {
  connect() {
    this.initial = this.serialize();
  }

  submit() {
    if (this.serialize() !== this.initial) this.element.requestSubmit();
  }

  serialize() {
    return new URLSearchParams(new FormData(this.element)).toString();
  }
}
