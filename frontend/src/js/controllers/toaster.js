import { Controller } from "@hotwired/stimulus";

//! connects to data-controller="toaster"
// Moves server-rendered toasts (templates/cotton/messages.html) out of their
// <template> into the toaster after load: live regions only announce content
// added after they exist. Basecoat's observer then inits and times each toast.
export default class extends Controller {
  static targets = ["messages"];

  messagesTargetConnected(template) {
    this.element.append(template.content);
    template.remove();
  }
}
