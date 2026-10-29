import { Controller } from "@hotwired/stimulus";

//! connects to data-controller="email-confirm"
// Asks before removing a selected email address (same behavior as allauth's account.js).
export default class extends Controller {
  submit(event) {
    if (event.submitter?.name === "action_remove") {
      if (!window.confirm("Do you really want to remove the selected email address?")) {
        event.preventDefault();
      }
    }
  }
}
