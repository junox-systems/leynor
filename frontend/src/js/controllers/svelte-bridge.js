import { Controller } from "@hotwired/stimulus";
import { mount, unmount } from "svelte";
import htmx from "htmx.org";

// ---------------------------------------------------------------------------
// svelte-bridge: the only thing allowed to connect Django and Svelte.
//
// Django renders HTML; Svelte renders interactive islands. This Stimulus
// controller sits between them: it finds the mount point a template declared,
// lazy-loads the Svelte component, and mounts it with data the server shaped.
//
// A template uses it like this:
//
//   {{ payload|json_script:"my-data" }}
//   <div data-controller="svelte-bridge"
//        data-svelte-bridge-component-value="app/Sidebar"
//        data-svelte-bridge-props-id-value="my-data"></div>
//
// The empty div is the parking space; the Svelte component takes it over on
// connect() and abandons it on disconnect().
// ---------------------------------------------------------------------------

// Treasure map of every Svelte component under ../svelte/, keyed by path
// without the extension ("app/Sidebar" -> ../svelte/app/Sidebar.svelte).
// import.meta.glob is lazy: a component's code is only downloaded when a page
// actually mounts it, never for pages that don't use it.
const components = import.meta.glob("../svelte/**/*.svelte");

export default class extends Controller {
  static values = {
    // Which component to mount, as a path relative to ../svelte/ without the
    // extension, matching a keys above: "app/Sidebar", "dashboard/Dashboard".
    component: String,
    // Inline JSON data, read from the data-svelte-bridge-props-value
    // attribute. Used on pages without a json_script parcel (e.g. the
    // marketing hero). Prefer propsId for anything server-shaped: putting
    // JSON in an HTML attribute is an escaping hazard.
    props: { type: Object, default: {} },
    // id of a {{ payload|json_script:"<id>" }} node to read props from.
    // Preferred route for server-rendered data.
    propsId: String,
  };

  // Props are read once at mount and never re-synced. Components treat them
  // as initial values; anything that must change later is client state
  // ($state) or a fetch, never a prop update.
  get resolvedProps() {
    // If the template gave us a json_script parcel id, the parcel is the
    // source of truth; fall back to the inline attribute otherwise.
    if (!this.propsIdValue) return this.propsValue;
    const el = document.getElementById(this.propsIdValue);
    if (!el) {
      // A missing node is a template bug, not a reason to take down the page.
      console.error(`svelte-bridge: no json_script node #${this.propsIdValue}`);
      return this.propsValue;
    }
    // The node is <script type="application/json">; textContent is the raw
    // JSON, so no attribute-escaping games.
    return JSON.parse(el.textContent);
  }

  // A permanent mount point (hx-preserve) survives boosted htmx navigation,
  // so its island must too: adopt it across visits instead of letting it
  // blink in and out.
  get isPermanent() {
    return this.element.hasAttribute("hx-preserve");
  }

  connect() {
    // Reset the race guard for this connect cycle (see the lazy load below).
    this.removed = false;
    const name = this.componentValue;
    if (!name) return;

    // htmx moves an hx-preserve element into the next page rather than
    // rebuilding it, which can make Stimulus disconnect and reconnect. The
    // existing instance is still valid — adopt it instead of mounting a
    // second copy, so the island never blinks or leaks listeners.
    if (this.element.__svelteIsland) {
      this.instance = this.element.__svelteIsland;
      return;
    }
    // Reconnected while the first chunk is still downloading: that load will
    // mount, so starting another would put two islands in one element.
    if (this.loading) return;

    const loader = components[`../svelte/${name}.svelte`];
    if (!loader) {
      // Unknown component value: a typo in the template. Log it loudly so the
      // mistake surfaces, but don't break the rest of the page.
      console.error(`svelte-bridge: no component found for ${name}.svelte`);
      return;
    }

    this.loading = true;
    loader()
      .then((mod) => {
        // The user may have navigated away while this chunk was downloading;
        // mounting into a detached element would leak an invisible island.
        if (this.removed || !this.element.isConnected) return;
        this.instance = mount(mod.default, {
          target: this.element,
          props: this.resolvedProps,
        });
        // htmx only scans the DOM it swaps in, so boost the links the island
        // just rendered (e.g. the sidebar nav inside the boosted shell).
        htmx.process(this.element);
        // Stamp the instance on the element so a future visit (re-connect
        // after an hx-preserve move) finds and adopts it instead of remounting.
        if (this.isPermanent) this.element.__svelteIsland = this.instance;
      })
      .catch((err) => {
        // Chunk failed to load or parse: surface it, keep the page alive.
        console.error(`svelte-bridge: failed to load ${name}.svelte`, err);
      })
      .finally(() => {
        this.loading = false;
      });
  }

  disconnect() {
    if (this.isPermanent) {
      // Mid-swap htmx detaches the element before reattaching it, so absence
      // right now proves nothing. Re-check on the next tick: still detached
      // means it was genuinely discarded (we left the shell) and must be torn
      // down, or its effects and document listeners leak.
      const element = this.element;
      const instance = this.instance;
      setTimeout(() => {
        if (!element.isConnected && instance) {
          unmount(instance);
          element.__svelteIsland = null;
        }
      }, 0);
      return;
    }

    // Non-permanent island: the page that owned it is going away for good, so
    // tear it down now, and make any in-flight lazy load see that we're gone.
    this.removed = true;
    if (this.instance) {
      unmount(this.instance);
      this.instance = null;
    }
  }
}
