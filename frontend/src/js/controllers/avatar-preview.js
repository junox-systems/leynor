import { Controller } from "@hotwired/stimulus";

//! connects to data-controller="avatar-preview"
// Avatar field (templates/users/widgets/avatar_input.html): the button opens
// the visually hidden file input, a picked file previews in the avatar before
// saving, and "Remove photo" previews the initials fallback.
export default class extends Controller {
  static targets = ["avatar", "input", "clear"];
  static values = { initial: String };

  connect() {
    this.original = this.avatarTarget.innerHTML;
  }

  disconnect() {
    this.revoke();
  }

  pick() {
    this.inputTarget.click();
  }

  preview() {
    const file = this.inputTarget.files[0];
    this.revoke();
    if (!file) {
      this.avatarTarget.innerHTML = this.original;
      return;
    }
    if (this.hasClearTarget) this.clearTarget.checked = false;
    this.url = URL.createObjectURL(file);
    const img = document.createElement("img");
    img.src = this.url;
    img.alt = "";
    this.avatarTarget.replaceChildren(img);
  }

  toggleClear() {
    if (!this.clearTarget.checked) {
      this.avatarTarget.innerHTML = this.original;
      return;
    }
    // Django rejects a file plus the clear box together; keep them exclusive.
    this.inputTarget.value = "";
    this.revoke();
    const span = document.createElement("span");
    span.textContent = this.initialValue;
    this.avatarTarget.replaceChildren(span);
  }

  revoke() {
    if (this.url) URL.revokeObjectURL(this.url);
    this.url = null;
  }
}
