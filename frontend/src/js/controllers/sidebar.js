import { Controller } from "@hotwired/stimulus";

// Mobile drawer + desktop icon rail for the Basecoat `.sidebar` component.
//
// All layout comes from Basecoat CSS, which reads two attributes off the
// `.sidebar` element:
//   data-sidebar-initialized — un-hides it below `md` (the no-JS baseline is
//                              `max-md:hidden`, so desktop works without JS)
//   aria-hidden="true"       — slides the nav out and drops the content margin
//
// Desktop keeps the sidebar open permanently, so `aria-hidden` is only ever
// set below `md`. There the toggle collapses it to an icon rail instead:
// `data-sidebar-collapsed` on <html>, styled in site.css, persisted in
// localStorage and re-applied pre-paint by base.html. Mounted on a wrapper so
// the app bar's toggle button — which lives outside the sidebar — can reach it.
export default class extends Controller {
  static targets = ["panel", "toggle"];
  static STORAGE_KEY = "sidebar";

  // initialize(), not connect(): Stimulus fires panelTargetConnected() BEFORE
  // connect(), and sync() needs this.desktop. Throwing there aborted every
  // later controller on the page — the theme toggle never connected.
  initialize() {
    // Tailwind's `md` breakpoint. Keep in sync with the CSS if that changes.
    this.desktop = window.matchMedia("(min-width: 48rem)");
    this.sync = this.sync.bind(this);
  }

  connect() {
    this.desktop.addEventListener("change", this.sync);
  }

  disconnect() {
    this.desktop.removeEventListener("change", this.sync);
  }

  // Initialise from the target callback, NOT connect(): the sidebar is
  // hx-preserve, so on a boosted visit this controller connects to the new
  // page before htmx has moved the preserved sidebar back into it. Reading
  // this.panelTarget in connect() throws "Missing target element".
  panelTargetConnected() {
    this.panelTarget.dataset.sidebarInitialized = "";
    this.sync();
  }

  // Open on desktop, closed on mobile — whenever the breakpoint changes.
  sync() {
    if (!this.hasPanelTarget) return;
    if (this.desktop.matches) {
      this.panelTarget.removeAttribute("aria-hidden");
    } else {
      this.panelTarget.setAttribute("aria-hidden", "true");
    }
    this.syncExpanded();
  }

  toggleTargetConnected() {
    this.syncExpanded();
  }

  // Desktop: expanded unless railed. Mobile: expanded while the drawer is open.
  syncExpanded() {
    if (!this.hasToggleTarget || !this.hasPanelTarget) return;
    const expanded = this.desktop.matches
      ? !("sidebarCollapsed" in document.documentElement.dataset)
      : this.panelTarget.getAttribute("aria-hidden") === "false";
    this.toggleTarget.setAttribute("aria-expanded", String(expanded));
  }

  close() {
    if (this.hasPanelTarget && !this.desktop.matches) {
      this.panelTarget.setAttribute("aria-hidden", "true");
      this.syncExpanded();
    }
  }

  toggle() {
    if (!this.hasPanelTarget) return;
    if (this.desktop.matches) {
      const collapsed = document.documentElement.toggleAttribute("data-sidebar-collapsed");
      try {
        localStorage.setItem(this.constructor.STORAGE_KEY, collapsed ? "collapsed" : "expanded");
      } catch {
        // Storage blocked: the rail still works, it just isn't remembered.
      }
    } else if (this.panelTarget.getAttribute("aria-hidden") === "false") {
      this.close();
    } else {
      this.panelTarget.setAttribute("aria-hidden", "false");
    }
    this.syncExpanded();
  }

  // The `.sidebar` element is itself the mobile backdrop; `nav` sits inside it.
  backdrop(event) {
    if (event.target === this.panelTarget) this.close();
  }
}
